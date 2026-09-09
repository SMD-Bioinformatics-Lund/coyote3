from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import mongomock
import pytest

from api.infra.mongo.repositories.ingest_jobs import IngestJobsRepository
from api.tasks import ingest


def test_resolve_sample_paths_uses_container_visible_manifest_paths(tmp_path):
    manifest = tmp_path / "incoming" / "sample" / "coyote3.yaml"
    manifest.parent.mkdir(parents=True)
    manifest.write_text("name: SAMPLE_1\n", encoding="utf-8")

    payload = ingest._resolve_relative_sample_paths(
        {
            "name": "SAMPLE_1",
            "vcf_files": "/data/coyote3/vcf/sample.vcf",
            "files": {
                "cnv": {"path": "/data/coyote3/cnv/sample.cnv.json"},
                "cov": "relative/sample.cov.json",
            },
        },
        manifest,
    )

    assert payload["vcf_files"] == "/data/coyote3/vcf/sample.vcf"
    assert payload["files"]["cnv"]["path"] == "/data/coyote3/cnv/sample.cnv.json"
    assert payload["files"]["cov"] == str((manifest.parent / "relative/sample.cov.json").resolve())


@pytest.mark.parametrize("retry_marker", [False, True])
def test_ingest_watch_directory_once_renames_manifest_done(tmp_path, monkeypatch, retry_marker):
    watch_dir = tmp_path / "incoming"
    sample_dir = watch_dir / "sample_1"
    sample_dir.mkdir(parents=True)
    manifest = sample_dir / "coyote3.yaml"
    manifest.write_text("name: SAMPLE_1\ncnv: files/sample.cnv.json\n", encoding="utf-8")

    captured_payloads = []

    class _Service:
        def parse_yaml_payload(self, raw):
            assert "SAMPLE_1" in raw
            return {"name": "SAMPLE_1", "cnv": "files/sample.cnv.json"}

        def ingest_sample_bundle(
            self, payload, *, allow_update=False, increment=False, record_completion=None
        ):
            captured_payloads.append(
                {
                    "payload": payload,
                    "allow_update": allow_update,
                    "increment": increment,
                }
            )
            result = {"sample_id": "sample-id", "sample_name": "SAMPLE_1"}
            record_completion(result, None)
            return result

    monkeypatch.setattr(ingest, "WATCH_INGEST_DIRECTORY", watch_dir)
    jobs = IngestJobsRepository(
        SimpleNamespace(ingest_jobs_collection=mongomock.MongoClient().test.ingest_jobs)
    )
    monkeypatch.setattr(ingest, "get_ingest_jobs_repository", lambda: jobs)
    monkeypatch.setattr(ingest.DefaultConfig, "COYOTE3_INGEST_WATCH_UPDATE_EXISTING", True)
    monkeypatch.setattr(ingest.DefaultConfig, "COYOTE3_INGEST_WATCH_INCREMENT", False)
    monkeypatch.setattr(ingest, "_ensure_worker_runtime", lambda: None)
    monkeypatch.setattr(ingest, "task_family_enabled", lambda _family: True)
    monkeypatch.setattr(ingest, "get_internal_ingest_service", lambda: _Service())
    if retry_marker:

        def unavailable_marker(*args, **kwargs):
            raise OSError("Synthetic marker failure")

        with monkeypatch.context() as marker_patch:
            marker_patch.setattr(Path, "rename", unavailable_marker)
            ingest.ingest_watch_directory_once.run()
        assert manifest.exists()
        assert len(captured_payloads) == 1

    result = ingest.ingest_watch_directory_once.run()

    assert result["scanned"] == 1
    assert result["failed"] == []
    assert result["ingested"][0]["done_path"].endswith("coyote3.yaml.done")
    assert not manifest.exists()
    assert (sample_dir / "coyote3.yaml.done").exists()
    assert captured_payloads == [
        {
            "payload": {
                "name": "SAMPLE_1",
                "cnv": str((sample_dir / "files/sample.cnv.json").resolve()),
            },
            "allow_update": True,
            "increment": False,
        }
    ]


def test_watch_preserves_manifest_when_disabled_midscan_then_processes_it(tmp_path, monkeypatch):
    """A midscan disable leaves the job pending and unacknowledged until enabled."""
    manifest = tmp_path / "coyote3.yaml"
    contents = "name: SYNTHETIC_A\n"
    manifest.write_text(contents, encoding="utf-8")
    collection = mongomock.MongoClient().test.ingest_jobs
    jobs = IngestJobsRepository(SimpleNamespace(ingest_jobs_collection=collection))
    result = {"sample_id": "synthetic-id", "sample_name": "SYNTHETIC_A"}

    def complete_bundle(payload, *, allow_update, increment, record_completion):
        record_completion(result, None)
        return result

    service = SimpleNamespace(
        parse_yaml_payload=Mock(return_value={"name": "SYNTHETIC_A"}),
        ingest_sample_bundle=Mock(side_effect=complete_bundle),
    )
    audit = Mock()
    monkeypatch.setattr(ingest, "WATCH_INGEST_DIRECTORY", tmp_path)
    monkeypatch.setattr(ingest, "WATCH_INGEST_LOCK_PATH", tmp_path / "scan.lock")
    monkeypatch.setattr(ingest, "_ensure_worker_runtime", lambda: None)
    monkeypatch.setattr(ingest, "get_ingest_jobs_repository", lambda: jobs)
    monkeypatch.setattr(ingest, "get_internal_ingest_service", lambda: service)
    monkeypatch.setattr(ingest, "_record_ingest_audit", audit)
    monkeypatch.setattr(ingest, "task_family_enabled", Mock(side_effect=[True, False, True, True]))

    deferred = ingest.ingest_watch_directory_once.run()

    assert deferred["scanned"] == 1
    assert deferred["ingested"] == []
    assert deferred["failed"] == []
    assert manifest.read_text(encoding="utf-8") == contents
    assert not list(tmp_path.glob("coyote3.yaml.*"))
    pending = collection.find_one()
    assert pending["state"] == "pending"
    service.ingest_sample_bundle.assert_not_called()
    audit.assert_not_called()

    completed = ingest.ingest_watch_directory_once.run()

    assert completed["scanned"] == 1
    assert completed["failed"] == []
    assert len(completed["ingested"]) == 1
    assert not manifest.exists()
    assert Path(completed["ingested"][0]["done_path"]).read_text(encoding="utf-8") == contents
    assert collection.count_documents({}) == 1
    assert jobs.get(pending["_id"])["state"] == "succeeded"
    service.ingest_sample_bundle.assert_called_once()
    assert [call.args[0] for call in audit.call_args_list].count("ingest.watch.succeeded") == 1


def test_watch_defers_manifest_changed_during_read(tmp_path, monkeypatch):
    manifest = tmp_path / "coyote3.yaml"
    manifest.write_text("name: SYNTHETIC_A\n", encoding="utf-8")
    original_read = Path.read_bytes

    def changing_read(path):
        content = original_read(path)
        path.write_text("name: SYNTHETIC_REPLACEMENT\n", encoding="utf-8")
        return content

    def unexpected_parse(raw):
        pytest.fail("An unstable manifest must not be parsed or submitted")

    monkeypatch.setattr(Path, "read_bytes", changing_read)
    monkeypatch.setattr(ingest, "WATCH_INGEST_DIRECTORY", tmp_path)
    monkeypatch.setattr(
        ingest,
        "get_internal_ingest_service",
        lambda: SimpleNamespace(parse_yaml_payload=unexpected_parse),
    )
    result = ingest._run_watch_directory_once(SimpleNamespace(request=SimpleNamespace(id="scan")))
    assert result["ingested"] == []
    assert result["failed"] == []
    assert manifest.exists()


def test_ingest_watch_directory_once_skips_when_another_scan_is_active(tmp_path, monkeypatch):
    lock_path = tmp_path / "ingest.lock"
    lock = ingest.FileLock(lock_path)

    monkeypatch.setattr(ingest, "WATCH_INGEST_LOCK_PATH", lock_path)
    monkeypatch.setattr(ingest, "_ensure_worker_runtime", lambda: None)
    monkeypatch.setattr(
        ingest,
        "_run_watch_directory_once",
        lambda self: {"status": "unexpected"},
    )

    with lock.acquire(timeout=0):
        result = ingest.ingest_watch_directory_once.run()

    assert result == {"status": "skipped", "reason": "already_running"}
