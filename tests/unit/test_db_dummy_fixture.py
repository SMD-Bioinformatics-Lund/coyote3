"""Validate the comprehensive dummy DB fixture against document contracts."""

from __future__ import annotations

import json
from pathlib import Path

from api.contracts.db_documents import COLLECTION_MODEL_ADAPTERS, validate_collection_document


def test_all_collections_dummy_fixture_validates():
    fixture_path = Path("tests/fixtures/db_dummy/all_collections_dummy.json")
    payload = json.loads(fixture_path.read_text(encoding="utf-8"))

    for collection, docs in payload.items():
        assert collection in COLLECTION_MODEL_ADAPTERS
        assert isinstance(docs, list)
        for doc in docs:
            validate_collection_document(collection, doc)
