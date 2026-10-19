"""Install packaged DNA/RNA starter workflows using configured deployment databases.

Run after the application baseline and indexes, before application startup. Without
--apply the command only inspects configuration. Existing samples are preserved.
"""

import argparse
import json
import os
from types import SimpleNamespace

from api.application.demo_installation import DemoInstallationService
from api.application.ingest.service import InternalIngestService
from api.config.loaders.collections import load_collection_section
from api.infra.mongo.connections import MongoConnections
from api.infra.mongo.ingest_gateway import IngestCollectionGateway
from api.infra.mongo.repositories.anno_vep import AnnoVepRepository
from api.infra.mongo.repositories.demo_installation import DemoInstallationRepository
from scripts.identity.sync_rbac_catalog import (
    DEFAULT_SEED_DATA_DIR,
    _load_ndjson,
    synchronize_rbac_catalog,
)


def install(actor: str, *, apply: bool = False) -> dict:
    """Plan or install the starter package and its installation-role grants.

    Args:
        actor: Existing administrator recorded as installer; no accounts are created.
        apply: Commit configuration and ingest both samples when True.

    Returns:
        Planned role changes and sample/configuration installation status.

    Raises:
        ValueError: The named installer is absent.
        AppError: Baseline, package identities or normal ingest validation fail.
    """
    connections = MongoConnections(os.environ)
    try:
        primary = connections.databases["primary"]
        identity = connections.databases["identity"]
        mapping = load_collection_section("primary")
        security = load_collection_section("identity")
        references = load_collection_section("knowledgebase")
        if not identity[security["users_collection"]].find_one(
            {
                "username": actor,
                "is_active": {"$ne": False},
                "roles": {"$in": ["admin", "sys_admin", "superuser"]},
            }
        ):
            raise ValueError("The installer must be an existing administrator")
        collections = {name: primary[name] for name in mapping.values()}
        collections["hgnc_genes"] = connections.databases["knowledgebase"][
            references["hgnc_collection"]
        ]
        ingest = InternalIngestService(
            collection_gateway=IngestCollectionGateway(collections=collections),
            anno_vep_repository=AnnoVepRepository(
                SimpleNamespace(anno_vep_collection=primary[mapping["anno_vep_collection"]])
            ),
            invalidate_dashboard_metrics=lambda: None,
        )
        repository = DemoInstallationRepository(primary)
        service = DemoInstallationService(repository, ingest)
        documents = service.configuration(actor, starter=True)
        if not repository.configuration_installed(documents, require_packaged=True):
            repository.preflight(documents)
        roles = [
            row
            for row in _load_ndjson(DEFAULT_SEED_DATA_DIR / "roles.seed.ndjson")
            if row["role_id"] in {"demo_installer", "admin", "sys_admin"}
        ]
        permissions = [
            row
            for row in _load_ndjson(DEFAULT_SEED_DATA_DIR / "permissions.seed.ndjson")
            if row["permission_id"] == "demo:install"
        ]
        grants = synchronize_rbac_catalog(
            identity,
            permissions_collection=security["permissions_collection"],
            roles_collection=security["roles_collection"],
            permission_docs=permissions,
            role_docs=roles,
            actor=actor,
            dry_run=not apply,
        )
        result = service.install_starter(actor) if apply else {"status": "plan_only"}
        return {
            **result,
            "roles": grants,
            "starter_samples": [row.model_dump() for row in service.plan().starter_samples],
        }
    finally:
        connections.close()


def main() -> None:
    """Read explicit operator intent and report the starter installation result."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--actor", required=True)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    print(json.dumps(install(args.actor, apply=args.apply), indent=2))


if __name__ == "__main__":
    main()
