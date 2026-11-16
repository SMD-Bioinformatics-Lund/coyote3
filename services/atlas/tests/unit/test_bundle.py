"""Reference integrity failures prevent loading or installation planning."""

import gzip
import hashlib
import json
import shutil

import pytest
from coyote_atlas.bundle import ReferenceBundle
from coyote_atlas.models import BundleManifest


@pytest.fixture
def bundle(tmp_path):
    """Create a small synthetic pack using one public reference row per dataset."""
    original = ReferenceBundle.packaged()
    shutil.copytree(original.directory, tmp_path / "reference")
    directory = tmp_path / "reference"
    manifest = original.inspect().model_dump(mode="json")
    for dataset in manifest["datasets"]:
        path = directory / dataset["path"]
        rows = gzip.decompress(path.read_bytes()).splitlines()
        # Retain all VEP rows so every content-addressed diagram remains referenced.
        if dataset["dataset_id"] == "hgnc_genes":
            path.write_bytes(gzip.compress(rows[0] + b"\n", mtime=0))
            dataset["records"] = 1
    _write_manifest(directory, manifest)
    return ReferenceBundle(directory)


def _write_manifest(directory, manifest):
    """Update synthetic resource digests after an intentional test mutation."""
    for entry in manifest["files"]:
        content = (directory / entry["path"]).read_bytes()
        entry["sha256"] = hashlib.sha256(content).hexdigest()
        entry["size_bytes"] = len(content)
    (directory / "manifest.json").write_text(json.dumps(manifest))


def test_packaged_bundle_matches_all_retained_resources():
    plan = ReferenceBundle.packaged().validate()
    assert plan.collections == {"hgnc_genes": 44084, "vep_metadata": 19, "vep_diagrams": 3}


def test_loading_preserves_original_reference_values_and_binary_diagrams(bundle):
    plan = bundle.plan()
    documents = bundle.load_documents()
    for dataset in plan.datasets:
        expected = [
            json.loads(line)
            for line in gzip.decompress((bundle.directory / dataset.path).read_bytes()).splitlines()
            if line.strip()
        ]
        assert documents[dataset.dataset_id] == expected
    for diagram in bundle.load_diagrams():
        assert isinstance(diagram["data"], bytes)
        assert hashlib.sha256(diagram["data"]).hexdigest() == diagram["_id"]


@pytest.mark.parametrize("change", ["missing", "untracked", "checksum", "symlink"])
def test_file_integrity_rejects_changes_before_parsing(bundle, tmp_path, change):
    target = bundle.directory / "vep_metadata.sources.json"
    if change == "missing":
        target.unlink()
    elif change == "untracked":
        (bundle.directory / "untracked.json").write_text("{}")
    elif change == "checksum":
        target.write_text("{}")
    else:
        outside = tmp_path / "outside.json"
        outside.write_bytes(target.read_bytes())
        target.unlink()
        target.symlink_to(outside)
    with pytest.raises(ValueError):
        bundle.validate()


@pytest.mark.parametrize(
    "change", ["count", "duplicate", "contract", "untracked_diagram", "unused_diagram"]
)
def test_valid_hashes_do_not_allow_invalid_content(bundle, change):
    manifest = bundle.inspect().model_dump(mode="json")
    hgnc = next(item for item in manifest["datasets"] if item["dataset_id"] == "hgnc_genes")
    path = bundle.directory / hgnc["path"]
    rows = [json.loads(line) for line in gzip.decompress(path.read_bytes()).splitlines()]
    if change == "count":
        hgnc["records"] = 2
    elif change == "duplicate":
        rows *= 2
        hgnc["records"] = 2
    elif change == "contract":
        rows[0].pop("hgnc_symbol")
    elif change == "unused_diagram":
        extra = "vep_diagrams/" + "0" * 64
        (bundle.directory / extra).write_bytes(b"extra")
        manifest["files"].append({"path": extra, "sha256": "0" * 64, "size_bytes": 5})
    else:
        diagram = next(
            item for item in manifest["files"] if item["path"].startswith("vep_diagrams/")
        )
        manifest["files"].remove(diagram)
        (bundle.directory / diagram["path"]).unlink()
    path.write_bytes(gzip.compress(b"\n".join(json.dumps(row).encode() for row in rows)))
    _write_manifest(bundle.directory, manifest)
    with pytest.raises(ValueError):
        bundle.validate()


@pytest.mark.parametrize("path", ["../outside", "/outside", "./file", "a/../b", "a\\b", "", "."])
def test_manifest_rejects_unsafe_paths(path):
    manifest = ReferenceBundle.packaged().inspect().model_dump(mode="json")
    manifest["files"][0]["path"] = path
    with pytest.raises(ValueError):
        BundleManifest.model_validate(manifest)


@pytest.mark.parametrize(
    "change",
    ["duplicate_file", "reserved", "missing_dataset", "duplicate_dataset_path", "missing_source"],
)
def test_manifest_rejects_inconsistent_inventories(change):
    manifest = ReferenceBundle.packaged().inspect().model_dump(mode="json")
    if change == "duplicate_file":
        manifest["files"].append(manifest["files"][0])
    elif change == "reserved":
        manifest["files"][0]["path"] = "manifest.json"
    elif change == "missing_dataset":
        manifest["datasets"].pop()
    elif change == "duplicate_dataset_path":
        manifest["datasets"][0]["path"] = manifest["datasets"][1]["path"]
    else:
        manifest["datasets"][0]["source"]["provenance_files"] = ["missing.json"]
    with pytest.raises(ValueError):
        BundleManifest.model_validate(manifest)
