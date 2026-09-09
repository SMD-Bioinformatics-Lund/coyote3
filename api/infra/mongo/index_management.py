"""Explicit MongoDB index inspection and maintenance operations."""

from __future__ import annotations

from copy import copy
from dataclasses import asdict, dataclass
from typing import Any

from api.infra.security.indexes import security_index_contracts


@dataclass(frozen=True)
class IndexContract:
    """Describe an expected index and its missing, present, or conflicting state."""

    repository: str
    collection: str
    name: str
    keys: tuple[tuple[str, int], ...]
    options: dict[str, Any]
    state: str


RETIRED_INDEXES: dict[str, tuple[str, ...]] = {
    "roles": ("role_id_active_1",),
    "permissions": ("permission_id_active_1",),
    "aspc": ("aspc_id_1", "asp_subpanel_environment_unique"),
    "asp": ("asp_id_1",),
    "isgl": ("isgl_id_1", "assays_1"),
}


class _ContractCollection:
    """Record create-index calls while exposing the current index inventory."""

    def __init__(self, collection: Any, repository: str):
        """Bind a collection for read-only index contract recording.

        Args:
            collection: Live collection whose index inventory is inspected.
            repository: Repository label attached to recorded contracts.
        """
        self._collection = collection
        self.repository = repository
        self.name = collection.name
        self.contracts: list[IndexContract] = []

    def list_indexes(self):
        """Read the wrapped collection's index inventory.

        Returns:
            The collection's index cursor without materializing it.
        """
        return self._collection.list_indexes()

    def create_index(self, keys, *, name: str, **options):
        """Record an expected index and compare it with the live named index.

        Args:
            keys: Ordered field and integer-direction pairs.
            name: Expected index name.
            **options: Index options; only semantic options affect comparison.

        Returns:
            The supplied index name, without creating or changing a database index.

        Notes:
            Appends a contract with missing, present, or conflict state.
        """
        current = {index["name"]: index for index in self._collection.list_indexes()}
        existing = current.get(name)
        expected_keys = tuple((str(field), int(direction)) for field, direction in keys)
        state = "missing"
        if existing is not None:
            actual_keys = tuple(
                (str(field), int(direction)) for field, direction in existing["key"].items()
            )
            expected_options = _semantic_options(options)
            actual_options = _semantic_options(existing)
            state = (
                "present"
                if actual_keys == expected_keys and actual_options == expected_options
                else "conflict"
            )
        self.contracts.append(
            IndexContract(
                repository=self.repository,
                collection=self.name,
                name=name,
                keys=expected_keys,
                options=_semantic_options(options),
                state=state,
            )
        )
        return name


class _ContractAdapter:
    """Intercept secondary collection handles used by repository index definitions."""

    def __init__(self, adapter: Any, repository: str, recorders: list[_ContractCollection]):
        """Bind read-only index recording for secondary collections.

        Args:
            adapter: Live adapter supplying repository collection handles.
            repository: Repository label included in each recorded contract.
            recorders: Shared list collecting every intercepted collection.
        """
        self._adapter = adapter
        self._repository = repository
        self._recorders = recorders
        self._collections: dict[str, _ContractCollection] = {}

    def __getattr__(self, name: str):
        """Wrap collection handles while forwarding other adapter configuration.

        Args:
            name: Adapter attribute requested by the repository.

        Returns:
            A read-only index recorder for collection handles, or the original value.
        """
        value = getattr(self._adapter, name)
        if not name.endswith("_collection"):
            return value
        if name not in self._collections:
            recorder = _ContractCollection(value, self._repository)
            self._collections[name] = recorder
            self._recorders.append(recorder)
        return self._collections[name]


def build_index_plan(adapter: Any) -> list[dict[str, Any]]:
    """Compare repository index contracts with the connected database."""
    plan: list[IndexContract] = []
    for repository_name, repository in adapter.iter_repositories():
        original = repository.get_collection()
        recorder = _ContractCollection(original, repository_name)
        recorders = [recorder]
        inspection_repository = copy(repository)
        inspection_repository.set_collection(recorder)
        if hasattr(repository, "adapter"):
            inspection_repository.adapter = _ContractAdapter(
                repository.adapter, repository_name, recorders
            )
        inspection_repository.ensure_indexes()
        for collection_recorder in recorders:
            plan.extend(collection_recorder.contracts)
    for contract in security_index_contracts(adapter.app.config):
        database = adapter.identity_db if contract.database == "identity" else adapter.coyote_db
        recorder = _ContractCollection(database[contract.collection], "security")
        recorder.create_index(list(contract.fields), name=contract.name, **contract.options)
        plan.extend(recorder.contracts)
    return [asdict(item) for item in plan]


def _semantic_options(options: dict[str, Any]) -> dict[str, Any]:
    """Keep options that alter index behavior and ignore driver command options."""
    meaningful = ("unique", "sparse", "expireAfterSeconds", "partialFilterExpression")
    return {key: options[key] for key in meaningful if key in options}


def known_retired_indexes(adapter: Any) -> list[dict[str, str]]:
    """Return obsolete indexes that are still present and require explicit retirement."""
    found: list[dict[str, str]] = []
    repositories = dict(adapter.iter_repositories())
    for repository_name, names in RETIRED_INDEXES.items():
        repository = repositories.get(repository_name)
        if repository is None:
            continue
        collection = repository.get_collection()
        existing = {index["name"] for index in collection.list_indexes()}
        for name in names:
            if name in existing:
                found.append(
                    {"repository": repository_name, "collection": collection.name, "name": name}
                )
    return found


def retire_index(
    adapter: Any, *, collection_name: str, index_name: str, repository_name: str | None = None
) -> None:
    """Drop one exact non-system index after caller-side confirmation."""
    if index_name == "_id_":
        raise ValueError("The MongoDB _id index cannot be retired")
    matches = [
        repository.get_collection()
        for name, repository in adapter.iter_repositories()
        if repository.get_collection().name == collection_name
        and (repository_name is None or name == repository_name)
    ]
    if not matches:
        raise ValueError(f"Unknown managed collection: {collection_name}")
    if len(matches) > 1:
        raise ValueError("Collection name is ambiguous; specify --repository from the index plan")
    collection = matches[0]
    existing = {index["name"] for index in collection.list_indexes()}
    if index_name not in existing:
        raise ValueError(f"Index {index_name!r} does not exist on {collection_name!r}")
    collection.drop_index(index_name)
