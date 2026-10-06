"""Complete-schema discovery on synthetic offline exports; no database connections."""

import json
import sqlite3
import sys

import pytest
from bson import BSON, Int64, ObjectId

from scripts.migration_common.commands import run
from scripts.migration_common.offline import (
    SOURCE_COLLECTIONS,
    SourceIndex,
    digest,
    prepare_source,
    private_json,
)
from scripts.migration_common.schema_inventory import inventory_export, observe, verify_review


def export_files(tmp_path, version, documents):
    """Write all required version-specific BSON files using synthetic documents."""
    directory = tmp_path / "export"
    directory.mkdir()
    for collection in SOURCE_COLLECTIONS[version]:
        (directory / f"{collection}.bson").write_bytes(
            b"".join(BSON.encode(record) for record in documents.get(collection, []))
        )
    return directory


def path(*parts):
    """Encode a tagged inventory path, using None for an array-member component."""
    return json.dumps(
        [["array"] if part is None else ["field", part] for part in parts], separators=(",", ":")
    )


@pytest.mark.parametrize("version", [2, 3])
def test_entire_export_including_last_record_and_later_array_members(tmp_path, version):
    records = [{"_id": ObjectId(), "value": index, "items": []} for index in range(1001)]
    records[-1].update(
        value=None,
        late_only={"key.with.dot": Int64(4)},
        items=[{}, {"rare": True}, {"rare": "yes"}, {"rare": None}],
    )
    directory = export_files(tmp_path, version, {"annotation": records})
    audit = tmp_path / "audit"
    manifest = inventory_export(directory, audit, version)
    assert manifest["complete"] is True
    assert manifest["collections"]["annotation"]["count"] == 1001
    assert manifest["collections"]["samples"]["count"] == 0
    with sqlite3.connect((audit / "schema.sqlite").as_uri() + "?mode=ro", uri=True) as connection:
        assert connection.execute(
            "SELECT documents_present, documents_missing FROM field_presence "
            "WHERE collection='annotation' AND path=?",
            (path("late_only", "key.with.dot"),),
        ).fetchone() == (1, 1000)
        assert connection.execute(
            "SELECT documents_present FROM paths WHERE collection='annotation' AND path=?",
            (path("items", None, "rare"),),
        ).fetchone() == (1,)
        assert dict(
            connection.execute(
                "SELECT bson_type, occurrences FROM types WHERE collection='annotation' AND path=?",
                (path("items", None, "rare"),),
            )
        ) == {"0x08": 1, "0x02": 1, "0x0a": 1}
        assert dict(
            connection.execute(
                "SELECT bson_type, occurrences FROM types WHERE collection='annotation' AND path=?",
                (path("value"),),
            )
        ) == {"0x10": 1000, "0x0a": 1}
        assert connection.execute(
            "SELECT occurrences FROM shapes WHERE collection='annotation' AND path=? AND fields='[]'",
            (path("items", None),),
        ).fetchone() == (1,)
    assert audit.stat().st_mode & 0o777 == 0o700
    assert (audit / "schema.sqlite").stat().st_mode & 0o777 == 0o600


def test_nested_arrays_and_literal_keys_do_not_collide():
    present, types, shapes = observe(
        {"a.b": 1, "a": {"b": None}, "nested": [[{"rare": Int64(1)}]], "[]": "value"}
    )
    assert path("a.b") in present and path("a", "b") in present
    assert types[(path("nested", None, None, "rare"), "0x12")] == 1
    assert shapes[(path("nested", None, None), '["rare"]')] == 1
    assert path("[]") != path(None)


@pytest.mark.parametrize("version", [2, 3])
def test_review_matches_full_snapshot_and_accounts_for_unprofiled_files(tmp_path, version):
    directory = export_files(tmp_path, version, {})
    (directory / "users.bson").write_bytes(BSON.encode({"_id": "SYNTHETIC"}))
    audit = tmp_path / "audit"
    manifest = inventory_export(directory, audit, version)
    index = tmp_path / "source.sqlite"
    prepare_source(directory, index, version)
    source = SourceIndex(index, version)
    assert source.fingerprint() == manifest["source_sha256"]
    with pytest.raises(ValueError, match="recorded operator review"):
        verify_review(source, audit, {})
    review = {
        "schema_audit": {
            "manifest_sha256": digest(manifest),
            "reviewed_by": "synthetic",
            "reviewed_on": "2026-10-06",
        }
    }
    with pytest.raises(ValueError, match="scope disposition"):
        verify_review(source, audit, review)
    review["schema_audit"]["unprofiled_files"] = {"users.bson": "Excluded identity collection"}
    assert verify_review(source, audit, review) == digest(manifest)
    with (directory / "annotation.bson").open("ab") as stream:
        stream.write(BSON.encode({"_id": ObjectId(), "rare_new_field": True}))
    next_index = tmp_path / "changed.sqlite"
    prepare_source(directory, next_index, version)
    changed = SourceIndex(next_index, version)
    with pytest.raises(ValueError, match="does not match"):
        verify_review(changed, audit, review)
    changed.close()
    with (audit / "schema.sqlite").open("ab") as stream:
        stream.write(b"changed")
    with pytest.raises(ValueError, match="altered"):
        verify_review(source, audit, review)
    source.close()


def test_corrupt_late_record_prevents_completion_manifest(tmp_path):
    directory = export_files(tmp_path, 2, {"annotation": [{"_id": ObjectId()}]})
    with (directory / "annotation.bson").open("ab") as stream:
        stream.write(b"\x10\x00\x00\x00broken")
    with pytest.raises(Exception):
        inventory_export(directory, tmp_path / "audit", 2)
    assert not (tmp_path / "audit/manifest.json").exists()


def test_cli_refuses_unreviewed_audit_before_conversion(tmp_path, monkeypatch, capsys):
    directory = export_files(tmp_path, 2, {})
    prepare_source(directory, tmp_path / "index.sqlite", 2)
    inventory_export(directory, tmp_path / "audit", 2)
    private_json(tmp_path / "review.json", {})
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "migrate_annotations.py",
            "--target-catalog",
            str(tmp_path / "target.json"),
            "--index",
            str(tmp_path / "index.sqlite"),
            "--schema-audit",
            str(tmp_path / "audit"),
            "--review",
            str(tmp_path / "review.json"),
            "--output",
            str(tmp_path / "bundle"),
        ],
    )
    assert run(2, "annotation") == 1
    assert "recorded operator review" in capsys.readouterr().err
    assert not (tmp_path / "bundle").exists()
