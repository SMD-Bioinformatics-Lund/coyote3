"""Validate the comprehensive dummy DB fixture against document contracts."""

from __future__ import annotations

import json
from pathlib import Path

import yaml

from api.contracts.schemas.registry import COLLECTION_MODEL_ADAPTERS, validate_collection_document
from api.contracts.schemas.samples import SamplesDoc


def _load_fixture_bundle(source: Path) -> dict[str, list[dict]]:
    if source.is_dir():
        payload: dict[str, list[dict]] = {}
        for file in sorted(source.glob("*.json")):
            payload[file.stem] = json.loads(file.read_text(encoding="utf-8"))
        return payload
    return json.loads(source.read_text(encoding="utf-8"))


def test_all_collections_dummy_fixture_validates():
    fixture_path = Path("demo_data/collections/all_collections_dummy")
    payload = _load_fixture_bundle(fixture_path)

    assert set(payload) == set(COLLECTION_MODEL_ADAPTERS), (
        "Demo collection fixtures must match the registered collection contracts. "
        f"Missing: {sorted(set(COLLECTION_MODEL_ADAPTERS) - set(payload))}; "
        f"unregistered: {sorted(set(payload) - set(COLLECTION_MODEL_ADAPTERS))}"
    )

    for collection, docs in payload.items():
        assert isinstance(docs, list)
        assert docs, f"Demo collection fixture '{collection}' must not be empty"
        for doc in docs:
            validate_collection_document(collection, doc)


def test_variant_transcript_annotations_use_the_versioned_collection() -> None:
    fixture_path = Path("demo_data/collections/all_collections_dummy")
    payload = _load_fixture_bundle(fixture_path)

    variant = payload["variants"][0]
    annotation = payload["anno_vep"][0]

    assert "CSQ" not in variant["INFO"]
    assert annotation["simple_id"] == variant["simple_id"]
    assert annotation["simple_id_hash"] == variant["simple_id_hash"]
    assert annotation["vep_version"]
    assert annotation["CSQ"]


def test_assay_panel_fixture_includes_required_files() -> None:
    fixture_path = Path("demo_data/collections/all_collections_dummy")
    payload = _load_fixture_bundle(fixture_path)
    assay_panels = payload["assay_specific_panels"]

    assert isinstance(assay_panels, list)
    assert assay_panels
    for doc in assay_panels:
        assert doc.get("required_files") == ["vcf_files"]
        validate_collection_document("assay_specific_panels", doc)


def test_demo_ingest_manifests_use_the_canonical_sample_contract() -> None:
    from api.application.ingest.collection_writes import parse_yaml_payload

    for manifest_path in (
        Path("demo_data/ingest/generic_case_control.yaml"),
        Path("demo_data/ingest/generic_rna_sample.yaml"),
    ):
        yaml_content = manifest_path.read_text(encoding="utf-8")
        payload = yaml.safe_load(yaml_content)

        assert isinstance(payload, dict)
        assert {"assay", "subpanel", "profile", "sequencing_technology"}.issubset(payload)
        assert not {"asp_id", "subpanel_id", "environment", "platform"}.intersection(payload)
        assert "files" not in payload
        assert "case" not in payload
        assert payload.get("case_id")
        assert payload.get("clarity_case_id")
        assert payload.get("sex") in {"female", "male", "unknown"}
        SamplesDoc.model_validate(parse_yaml_payload(yaml_content))


def test_demo_dna_ingest_bundle_paths_resolve_from_manifest_directory() -> None:
    manifest_path = Path("demo_data/ingest/generic_case_control.yaml")
    payload = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))

    assert isinstance(payload, dict)
    for file_key in ("vcf_files", "cnv", "cnvprofile", "cov"):
        declared_path = payload.get(file_key)
        assert isinstance(declared_path, str)
        assert not Path(declared_path).is_absolute()
        assert (manifest_path.parent / declared_path).is_file()
