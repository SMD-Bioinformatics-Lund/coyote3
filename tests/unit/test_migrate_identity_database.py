"""Tests for the dedicated identity database migration."""

from __future__ import annotations

from pathlib import Path

from scripts.identity.migrate_identity_database import identity_collections


def test_identity_collection_mapping_is_explicit(tmp_path: Path) -> None:
    config = tmp_path / "collections.toml"
    config.write_text(
        '[primary]\nsamples_collection = "samples"\n'
        '[identity]\nusers_collection = "users"\naudit_events_collection = "audit_events"\n'
        '[knowledgebase]\ncivic_collection = "civic"\n'
        '[bam]\nbam_samples = "samples"\n',
        encoding="utf-8",
    )

    assert identity_collections(config) == {
        "users_collection": "users",
        "audit_events_collection": "audit_events",
    }
