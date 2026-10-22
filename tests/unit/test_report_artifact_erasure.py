"""Report erasure stays within managed storage and survives interrupted cleanup."""

import json
from pathlib import Path
from types import SimpleNamespace

import mongomock
import pytest
from fastapi import HTTPException
from pymongo.errors import AutoReconnect
from starlette.requests import Request

from api.domain.core.exceptions import AppError
from api.infra.mongo.repositories import report_artifact_erasure as erasure
from api.interfaces.http.admin.resources import samples
from api.security import access
from tests.fixtures.api.permission_catalog import PermissionCatalog


@pytest.fixture
def reports(monkeypatch):
    """Use isolated collections and a deterministic transaction adapter for file tests."""
    monkeypatch.setattr(erasure, "run_transaction", lambda client, callback: callback(None))
    monkeypatch.setattr(erasure, "enqueue_audit", lambda *args, **kwargs: None)
    monkeypatch.setenv("IDENTITY_DB", "synthetic_identity")
    monkeypatch.setenv("IDENTITY_MONGO_URI", "mongodb://localhost:27017")
    return mongomock.MongoClient().synthetic.reports


def queue(reports, root, path):
    """Capture one generated synthetic report under the sample ownership predicate."""
    reports.insert_one({"sample_oid": "owned", "filepath": str(path)})
    assert (
        erasure.enqueue_report_erasure(
            reports, {"sample_oid": "owned"}, root=root, sample_id="owned", session=None
        )
        == 1
    )
    reports.delete_many({"sample_oid": "owned"})


def test_committed_erasure_is_idempotent_and_preserves_other_files(reports, tmp_path):
    report = tmp_path / "report.html"
    report.write_text("synthetic report")
    unrelated = tmp_path / "other.pdf"
    unrelated.write_text("other owner")
    queue(reports, tmp_path, report)
    assert report.exists()
    assert erasure.erase_pending_reports(reports, root=tmp_path)["completed"] == 1
    assert not report.exists()
    assert unrelated.exists()
    assert erasure.erase_pending_reports(reports, root=tmp_path)["completed"] == 0


def test_failed_unlink_is_retried(reports, tmp_path, monkeypatch):
    report = tmp_path / "report.pdf"
    report.write_text("synthetic")
    queue(reports, tmp_path, report)
    original = erasure._unlink_report

    def deny(*args):
        """Emulate a temporary filesystem permission failure."""
        raise PermissionError("synthetic")

    monkeypatch.setattr(erasure, "_unlink_report", deny)
    assert erasure.erase_pending_reports(reports, root=tmp_path)["retry_required"] == 1
    failed = reports.database.report_artifact_erasure.find_one()
    assert failed["attempts"] == 1
    assert failed["last_error"] == "permission_denied"
    assert failed["last_attempt"] is not None
    assert report.exists()
    monkeypatch.setattr(erasure, "_unlink_report", original)
    assert erasure.erase_pending_reports(reports, root=tmp_path)["completed"] == 1


def test_missing_file_after_interrupted_acknowledgement_completes(reports, tmp_path):
    queue(reports, tmp_path, tmp_path / "already-removed.pdf")
    assert erasure.erase_pending_reports(reports, root=tmp_path)["completed"] == 1


def test_database_acknowledgement_failure_retains_erasure_job(reports, tmp_path, monkeypatch):
    """A crash after unlink leaves a job that can safely acknowledge the missing file."""
    path = tmp_path / "report.html"
    path.write_text("synthetic")
    queue(reports, tmp_path, path)

    def fail(client, callback):
        """Fail before database acknowledgement without undoing the completed unlink."""
        raise AutoReconnect("synthetic")

    monkeypatch.setattr(erasure, "run_transaction", fail)
    with pytest.raises(AutoReconnect):
        erasure.erase_pending_reports(reports, root=tmp_path)
    assert not path.exists()
    assert reports.database.report_artifact_erasure.count_documents({}) == 1
    monkeypatch.setattr(erasure, "run_transaction", lambda client, callback: callback(None))
    assert erasure.erase_pending_reports(reports, root=tmp_path)["completed"] == 1


def test_other_deployment_cannot_drain_erasure_jobs(reports, tmp_path, monkeypatch):
    path = tmp_path / "report.pdf"
    path.write_text("synthetic")
    queue(reports, tmp_path, path)
    monkeypatch.setenv("IDENTITY_DB", "another_identity")
    assert erasure.erase_pending_reports(reports, root=tmp_path)["completed"] == 0
    assert path.exists()


def test_missing_storage_keeps_pending_jobs(reports, tmp_path):
    root = tmp_path / "reports"
    root.mkdir()
    queue(reports, root, root / "report.pdf")
    root.rmdir()
    assert erasure.erase_pending_reports(reports, root=root)["retry_required"] == 1
    assert reports.database.report_artifact_erasure.count_documents({}) == 1
    assert (
        reports.database.report_artifact_erasure.find_one()["last_error"] == "storage_unavailable"
    )
    assert erasure.report_erasure_backlog(reports.database) == {
        "pending": 1,
        "failed_pending": 1,
        "oldest_age_seconds": 0,
    }


@pytest.mark.parametrize("reason", ["root_changed", "storage_identity_changed", "still_referenced"])
def test_guard_failures_record_actionable_reason_without_erasing(reports, tmp_path, reason):
    path = tmp_path / "retained.pdf"
    path.write_text("synthetic")
    queue(reports, tmp_path, path)
    jobs = reports.database.report_artifact_erasure
    if reason == "root_changed":
        jobs.update_one({}, {"$set": {"root": "/different-root"}})
    elif reason == "storage_identity_changed":
        jobs.update_one({}, {"$set": {"root_inode": -1}})
    else:
        reports.insert_one({"sample_oid": "other", "filepath": str(path)})
    result = erasure.erase_pending_reports(reports, root=tmp_path)
    assert result["pending"] == result["failed_pending"] == 1
    assert jobs.find_one()["last_error"] == reason
    assert path.exists()


def test_outside_and_shared_paths_block_deletion(reports, tmp_path):
    outside = tmp_path.parent / "outside.html"
    reports.insert_one({"sample_oid": "owned", "filepath": str(outside)})
    with pytest.raises(AppError, match="reconciliation"):
        erasure.enqueue_report_erasure(
            reports, {"sample_oid": "owned"}, root=tmp_path, sample_id="owned", session=None
        )
    reports.delete_many({})
    path = tmp_path / "shared.html"
    reports.insert_many(
        [{"sample_oid": owner, "filepath": str(path)} for owner in ("owned", "other")]
    )
    with pytest.raises(AppError, match="another sample"):
        erasure.enqueue_report_erasure(
            reports, {"sample_oid": "owned"}, root=tmp_path, sample_id="owned", session=None
        )


def test_replaced_parent_symlink_cannot_erase_external_file(reports, tmp_path):
    root = tmp_path / "reports"
    folder = root / "group"
    folder.mkdir(parents=True)
    queue(reports, root, folder / "report.pdf")
    folder.rmdir()
    outside = tmp_path / "external"
    outside.mkdir()
    target = outside / "report.pdf"
    target.write_text("must remain")
    folder.symlink_to(outside, target_is_directory=True)
    assert erasure.erase_pending_reports(reports, root=root)["retry_required"] == 1
    assert target.read_text() == "must remain"


@pytest.mark.parametrize("role", ["admin", "superuser", "viewer", "sysadmin"])
def test_sample_deletion_dependency_enforces_seeded_role_permissions(monkeypatch, role):
    """Exercise the actual deletion route dependency with the configured role catalog."""
    root = Path(__file__).resolve().parents[2]
    roles = [
        json.loads(line)
        for line in (root / "api/config/bootstrap/rbac/roles.seed.ndjson").read_text().splitlines()
        if line
    ]
    assert {row["role_id"] for row in roles if "sample:delete:global" in row["permissions"]} == {
        "admin",
        "superuser",
    }
    user = access.ApiUser(
        id="synthetic",
        username="synthetic",
        email="test@example.org",
        fullname="Synthetic",
        roles=[role],
        role=role,
        permissions=[],
        access_level=1000000 if role == "superuser" else 0,
        asp_ids=[],
        asp_groups=[],
        envs=[],
        asp_map={},
        auth_type=["local"],
    )
    monkeypatch.setattr(access, "_decode_session_user", lambda request: user)
    monkeypatch.setattr(access, "_audit_access_event", lambda **kwargs: None)
    monkeypatch.setattr(
        access, "get_roles_repository", lambda: SimpleNamespace(get_all_roles=lambda: roles)
    )
    monkeypatch.setattr(access, "get_permissions_repository", PermissionCatalog)
    route = next(route for route in samples.router.routes if "DELETE" in route.methods)
    dependency = next(item.call for item in route.dependant.dependencies if item.name == "user")
    request = Request(
        {
            "type": "http",
            "method": "DELETE",
            "path": "/api/v1/resources/samples/synthetic",
            "headers": [],
        }
    )
    if role in {"admin", "superuser"}:
        generator = dependency(request)
        assert next(generator) == user
        generator.close()
    else:
        with pytest.raises(HTTPException) as denied:
            next(dependency(request))
        assert denied.value.status_code == 403
