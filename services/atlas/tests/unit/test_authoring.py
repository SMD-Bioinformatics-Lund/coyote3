"""Reference review copies keep installed resources immutable and produce checked manifests."""

import hashlib
import json

import pytest
from coyote_atlas.authoring import draft_bundle
from coyote_atlas.bundle import ReferenceBundle


def test_draft_refreshes_inventory_and_preserves_installed_resources(tmp_path):
    original = ReferenceBundle.packaged()
    before = original.plan()
    output = tmp_path / "review"
    with draft_bundle(output, "review-2") as directory:
        assert directory == output
        source = directory / "vep_metadata.sources.json"
        data = json.loads(source.read_text())
        data["review_note"] = "Synthetic authoring exercise"
        source.write_text(json.dumps(data))
        (directory / "vep_diagrams" / ("0" * 64)).write_bytes(b"unreferenced")
    revised = ReferenceBundle(output)
    after = revised.plan()
    assert after.bundle_version == "review-2"
    assert after.manifest_sha256 != before.manifest_sha256
    assert after.collections == before.collections
    assert not (output / "vep_diagrams" / ("0" * 64)).exists()
    assert original.plan() == before
    for dataset in after.datasets:
        assert (
            dataset.version
            == "sha256:" + hashlib.sha256((output / dataset.path).read_bytes()).hexdigest()
        )


@pytest.mark.parametrize("version", ["", "  ", "1.0.0"])
def test_draft_rejects_unversioned_or_unchanged_copy(tmp_path, version):
    output = tmp_path / "review"
    with pytest.raises(ValueError):
        with draft_bundle(output, version):
            pytest.fail("Invalid version entered the authoring block")
    assert not output.exists()


def test_draft_cannot_replace_an_existing_directory(tmp_path):
    with pytest.raises(FileExistsError):
        with draft_bundle(tmp_path, "review-2"):
            pytest.fail("Existing directory entered the authoring block")


def test_invalid_reference_copy_is_not_accepted(tmp_path):
    output = tmp_path / "review"
    with pytest.raises((OSError, ValueError)):
        with draft_bundle(output, "review-2"):
            (output / "hgnc_genes.seed.ndjson.gz").write_bytes(b"invalid gzip")
