"""Validate the comprehensive dummy DB fixture against document contracts."""

from __future__ import annotations

import json
from pathlib import Path

from api.contracts.schemas.registry import COLLECTION_MODEL_ADAPTERS, validate_collection_document


def _load_fixture_bundle(source: Path) -> dict[str, list[dict]]:
    if source.is_dir():
        payload: dict[str, list[dict]] = {}
        for file in sorted(source.glob("*.json")):
            payload[file.stem] = json.loads(file.read_text(encoding="utf-8"))
        return payload
    return json.loads(source.read_text(encoding="utf-8"))


def test_all_collections_dummy_fixture_validates():
    fixture_path = Path("tests/fixtures/db_dummy/all_collections_dummy")
    payload = _load_fixture_bundle(fixture_path)

    strict_ready = {
        "cnvs",
        "mane_select",
        "oncokb_genes",
        "permissions",
        "refseq_canonical",
        "roles",
        "samples",
    }

    for collection, docs in payload.items():
        if collection not in strict_ready:
            continue
        assert collection in COLLECTION_MODEL_ADAPTERS
        assert isinstance(docs, list)
        for doc in docs:
            validate_collection_document(collection, doc)
