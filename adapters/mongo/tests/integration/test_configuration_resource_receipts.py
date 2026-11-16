"""Pinned resource content remains stable and fails closed when invalid."""

from datetime import datetime, timezone

from bson import ObjectId
from coyote.application.common.release_resources import assay_resource, capture_assay_resource


def test_persisted_release_digest_preserves_canonical_bson_encoding():
    """Existing digests retain BSON IDs, integer types, timestamps, null and key ordering."""
    content = {
        "_id": ObjectId("000000000000000000000001"),
        "version": 1,
        "approved": True,
        "time": datetime(2026, 1, 2, 3, 4, 5, tzinfo=timezone.utc),
        "genes": ["TP53"],
        "value": None,
    }
    release = capture_assay_resource(content)
    assert release["content_hash"] == (
        "4aec49a35a160a08a041f9cdeef8a83d2f961228964a0cd20f9fcb381992ae31"
    )
    assert capture_assay_resource(dict(reversed(content.items()))) == release


def test_assay_revision_is_independent_of_authoring_and_runtime_edits():
    panel = {
        "_id": ObjectId(),
        "asp_id": "demo-solid_gmsv3",
        "asp_group": "solid",
        "version": 1,
        "covered_genes": {"TP53": True},
    }
    configuration = {
        "asp_id": "demo-solid_gmsv3",
        "asp_group": "solid",
        "assay_resource_release": capture_assay_resource(panel),
    }
    panel["covered_genes"]["BRAF"] = True
    loaded = assay_resource(configuration)
    assert loaded["covered_genes"] == {"TP53": True}
    loaded["covered_genes"].clear()
    assert assay_resource(configuration)["covered_genes"] == {"TP53": True}
