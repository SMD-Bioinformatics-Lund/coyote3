"""Synthetic reusable fixtures for package-owned behavior tests."""

from types import SimpleNamespace

from bson.codec_options import CodecOptions

from tests.fixtures.mongo_settings import audit_context


class FakeCollection:
    def __init__(self, name: str, indexes: list[dict]):
        self.name = name
        self.indexes = indexes
        self.dropped: list[str] = []
        self.codec_options = CodecOptions()

    def with_options(self, *, codec_options):
        """Support read-only codec selection without permitting index writes."""
        self.codec_options = codec_options
        return self

    def list_indexes(self):
        return list(self.indexes)

    def drop_index(self, name: str):
        self.dropped.append(name)


class FakeRepository:
    def __init__(self, collection: FakeCollection):
        self.collection = collection

    def get_collection(self):
        return self.collection

    def set_collection(self, collection):
        self.collection = collection

    def ensure_indexes(self):
        self.collection.create_index([("sample_id", 1)], name="sample_id_1", unique=True)
        self.collection.create_index([("updated_on", -1)], name="updated_on_desc_1")


def adapter_for(repository: FakeRepository):
    security_collections = {
        "api_sessions": FakeCollection("api_sessions", []),
        "service_tokens": FakeCollection("service_tokens", []),
        "audit_events": FakeCollection("audit_events", []),
        "operational_audit_events": FakeCollection("operational_audit_events", []),
        "app_controls": FakeCollection("app_controls", []),
        "report_artifact_erasure": FakeCollection("report_artifact_erasure", []),
    }
    primary_database = type(
        "FakeDatabase", (), {"__getitem__": lambda self, key: security_collections[key]}
    )()
    identity_database = type(
        "FakeIdentityDatabase", (), {"__getitem__": lambda self, key: security_collections[key]}
    )()
    return SimpleNamespace(
        iter_repositories=lambda: iter([("samples", repository)]),
        app=SimpleNamespace(audit=audit_context(), config={}),
        coyote_db=primary_database,
        identity_db=identity_database,
    )
