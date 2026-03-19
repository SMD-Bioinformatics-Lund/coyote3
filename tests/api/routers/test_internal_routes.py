"""Behavior tests for internal API routes."""

from __future__ import annotations

from types import SimpleNamespace

from api.routers import internal


def test_get_role_levels_internal_returns_id_to_level_map(monkeypatch):
    """Test get role levels internal returns id to level map.

    Args:
        monkeypatch: Value for ``monkeypatch``.

    Returns:
        The function result.
    """
    calls = {"token": 0}

    monkeypatch.setattr(
        internal, "_require_internal_token", lambda _request: calls.__setitem__("token", 1)
    )
    monkeypatch.setattr(
        internal.util,
        "common",
        SimpleNamespace(convert_to_serializable=lambda payload: payload),
        raising=False,
    )
    repository = SimpleNamespace(
        get_all_roles=lambda: [{"role_id": "admin", "level": 99}, {"role_id": "viewer"}]
    )

    payload = internal.get_role_levels_internal(request=object(), repository=repository)

    assert calls["token"] == 1
    assert payload["status"] == "ok"
    assert payload["role_levels"] == {"admin": 99, "viewer": 0}


def test_get_isgl_meta_internal_reads_adhoc_and_display_name(monkeypatch):
    """Test get isgl meta internal reads adhoc and display name.

    Args:
        monkeypatch: Value for ``monkeypatch``.

    Returns:
        The function result.
    """
    calls = {"token": 0}

    monkeypatch.setattr(
        internal, "_require_internal_token", lambda _request: calls.__setitem__("token", 1)
    )
    monkeypatch.setattr(
        internal.util,
        "common",
        SimpleNamespace(convert_to_serializable=lambda payload: payload),
        raising=False,
    )
    repository = SimpleNamespace(
        is_isgl_adhoc=lambda _isgl_id: True,
        get_isgl_display_name=lambda _isgl_id: "Focus Panel",
    )

    payload = internal.get_isgl_meta_internal("ISGL123", request=object(), repository=repository)

    assert calls["token"] == 1
    assert payload == {
        "status": "ok",
        "isgl_id": "ISGL123",
        "is_adhoc": True,
        "display_name": "Focus Panel",
    }


def test_ingest_sample_bundle_internal_accepts_spec(monkeypatch):
    """Test sample-bundle ingest route forwards structured spec payload."""
    calls: dict[str, object] = {}

    monkeypatch.setattr(
        internal.util,
        "common",
        SimpleNamespace(convert_to_serializable=lambda payload: payload),
        raising=False,
    )

    def _ingest(payload, *, allow_update=False):
        calls["payload"] = payload
        calls["allow_update"] = allow_update
        return {
            "status": "ok",
            "sample_id": "abc",
            "sample_name": "S1",
            "written": {"snvs": 1},
            "data_counts": {"snvs": 1},
        }

    monkeypatch.setattr(internal.InternalIngestService, "ingest_sample_bundle", _ingest)

    payload = internal.InternalIngestSampleBundleRequest(
        spec={"name": "S1", "genome_build": 38, "vcf_files": "/tmp/a.vcf"}
    )
    response = internal.ingest_sample_bundle_internal(payload=payload)

    assert calls["payload"] == {
        "name": "S1",
        "genome_build": 38,
        "vcf_files": "/tmp/a.vcf",
        "increment": False,
    }
    assert response["status"] == "ok"


def test_ingest_sample_bundle_internal_accepts_yaml(monkeypatch):
    """Test sample-bundle ingest route accepts YAML request body."""
    monkeypatch.setattr(
        internal.util,
        "common",
        SimpleNamespace(convert_to_serializable=lambda payload: payload),
        raising=False,
    )
    monkeypatch.setattr(
        internal.InternalIngestService,
        "parse_yaml_payload",
        lambda text: {"name": "S2", "vcf_files": "/tmp/s2.vcf", "from_yaml": text},
    )
    monkeypatch.setattr(
        internal.InternalIngestService,
        "ingest_sample_bundle",
        lambda payload, *, allow_update=False: {
            "status": "ok",
            "sample_id": "def",
            "sample_name": payload["name"],
            "written": {},
            "data_counts": {},
        },
    )

    payload = internal.InternalIngestSampleBundleRequest(yaml_content="name: S2")
    response = internal.ingest_sample_bundle_internal(payload=payload)

    assert response["sample_name"] == "S2"


def test_ingest_sample_bundle_internal_rejects_invalid_shape(monkeypatch):
    """Test sample-bundle ingest route rejects missing/duplicate body forms."""
    empty_payload = internal.InternalIngestSampleBundleRequest()
    try:
        internal.ingest_sample_bundle_internal(payload=empty_payload)
        assert False, "Expected ValueError for empty payload"
    except ValueError as exc:
        assert "spec" in str(exc)

    dual_payload = internal.InternalIngestSampleBundleRequest(
        spec={"name": "X"},
        yaml_content="name: X",
    )
    try:
        internal.ingest_sample_bundle_internal(payload=dual_payload)
        assert False, "Expected ValueError for duplicate payload forms"
    except ValueError as exc:
        assert "only one" in str(exc)


def test_ingest_sample_bundle_internal_requires_edit_sample_permission_for_update(monkeypatch):
    """Test update mode requires authenticated user with edit_sample permission."""
    calls = {"enforced": 0, "allow_update": None}
    monkeypatch.setattr(
        internal,
        "_enforce_access",
        lambda _user, permission=None, min_level=None, min_role=None: calls.__setitem__(
            "enforced", 1
        ),
    )
    monkeypatch.setattr(
        internal.util,
        "common",
        SimpleNamespace(convert_to_serializable=lambda payload: payload),
        raising=False,
    )

    def _ingest(payload, *, allow_update=False):
        calls["allow_update"] = allow_update
        return {
            "status": "ok",
            "sample_id": "upd-1",
            "sample_name": payload["name"],
            "written": {},
            "data_counts": {},
        }

    monkeypatch.setattr(internal.InternalIngestService, "ingest_sample_bundle", _ingest)
    payload = internal.InternalIngestSampleBundleRequest(
        spec={"name": "S3", "vcf_files": "/tmp/s3.vcf"},
        update_existing=True,
    )
    response = internal.ingest_sample_bundle_internal(payload=payload, user=object())
    assert calls["enforced"] == 1
    assert calls["allow_update"] is True
    assert response["sample_id"] == "upd-1"


def test_ingest_collection_document_internal_forwards_payload(monkeypatch):
    """Single collection ingest route should forward request payload."""
    monkeypatch.setattr(
        internal.util,
        "common",
        SimpleNamespace(convert_to_serializable=lambda payload: payload),
        raising=False,
    )
    monkeypatch.setattr(
        internal.InternalIngestService,
        "insert_collection_document",
        lambda *, collection, document, ignore_duplicate=False: {
            "status": "ok",
            "collection": collection,
            "inserted_count": 1,
            "inserted_id": "abc123",
        },
    )
    payload = internal.InternalCollectionInsertRequest(
        collection="hgnc_genes",
        document={"hgnc_id": "HGNC:5", "hgnc_symbol": "A1BG"},
    )
    response = internal.ingest_collection_document_internal(payload=payload)
    assert response["collection"] == "hgnc_genes"
    assert response["inserted_count"] == 1


def test_ingest_collection_documents_internal_forwards_payload(monkeypatch):
    """Bulk collection ingest route should forward request payload."""
    monkeypatch.setattr(
        internal.util,
        "common",
        SimpleNamespace(convert_to_serializable=lambda payload: payload),
        raising=False,
    )
    monkeypatch.setattr(
        internal.InternalIngestService,
        "insert_collection_documents",
        lambda *, collection, documents, ignore_duplicates=False: {
            "status": "ok",
            "collection": collection,
            "inserted_count": len(documents),
            "inserted_id": None,
        },
    )
    payload = internal.InternalCollectionBulkInsertRequest(
        collection="hgnc_genes",
        documents=[
            {"hgnc_id": "HGNC:5", "hgnc_symbol": "A1BG"},
            {"hgnc_id": "HGNC:6", "hgnc_symbol": "A1CF"},
        ],
    )
    response = internal.ingest_collection_documents_internal(payload=payload)
    assert response["collection"] == "hgnc_genes"
    assert response["inserted_count"] == 2


def test_list_supported_ingest_collections_internal(monkeypatch):
    """List supported ingest collections route should expose registered collection names."""
    monkeypatch.setattr(
        internal.util,
        "common",
        SimpleNamespace(convert_to_serializable=lambda payload: payload),
        raising=False,
    )
    monkeypatch.setattr(
        internal.InternalIngestService,
        "list_supported_collections",
        lambda: ["asp_configs", "hgnc_genes", "samples"],
    )

    response = internal.list_supported_ingest_collections_internal()
    assert response["status"] == "ok"
    assert response["collections"] == ["asp_configs", "hgnc_genes", "samples"]
