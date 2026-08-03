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


def test_ingest_watch_directory_once_renames_manifest_done(tmp_path, monkeypatch):
    watch_dir = tmp_path / "incoming"
    sample_dir = watch_dir / "sample_1"
    sample_dir.mkdir(parents=True)
    manifest = sample_dir / "coyote3.yaml"
    manifest.write_text("name: SAMPLE_1\ncnv: files/sample.cnv.json\n", encoding="utf-8")

    captured_payloads = []
    enrichment_requests = []

    class _Service:
        def parse_yaml_payload(self, raw):
            assert "SAMPLE_1" in raw
            return {"name": "SAMPLE_1", "cnv": "files/sample.cnv.json"}

        def ingest_sample_bundle(self, payload, *, allow_update=False, increment=False):
            captured_payloads.append(
                {
                    "payload": payload,
                    "allow_update": allow_update,
                    "increment": increment,
                }
            )
            return {"sample_id": "sample-id", "sample_name": "SAMPLE_1"}

    monkeypatch.setattr(ingest, "WATCH_INGEST_DIRECTORY", watch_dir)
    monkeypatch.setattr(ingest.DefaultConfig, "COYOTE3_INGEST_WATCH_UPDATE_EXISTING", True)
    monkeypatch.setattr(ingest.DefaultConfig, "COYOTE3_INGEST_WATCH_INCREMENT", False)
    monkeypatch.setattr(ingest, "_ensure_worker_runtime", lambda: None)
    monkeypatch.setattr(ingest, "task_family_enabled", lambda _family: True)
    monkeypatch.setattr(ingest, "get_internal_ingest_service", lambda: _Service())
    monkeypatch.setattr(
        ingest,
        "_queue_public_oncokb_enrichment",
        lambda result: enrichment_requests.append(
            {"result": result, "manifest_finalized": not manifest.exists()}
        )
        or "enrichment-task-id",
    )
    result = ingest.ingest_watch_directory_once.run()

    assert result["scanned"] == 1
    assert result["failed"] == []
    assert result["ingested"][0]["done_path"].endswith("coyote3.yaml.done")
    assert not manifest.exists()
    assert (sample_dir / "coyote3.yaml.done").exists()
    assert result["ingested"][0]["enrichment_task_id"] == "enrichment-task-id"
    assert enrichment_requests == [
        {
            "result": {"sample_id": "sample-id", "sample_name": "SAMPLE_1"},
            "manifest_finalized": True,
        }
    ]
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


def test_public_oncokb_enrichment_runs_as_independent_task(monkeypatch):
    class _Service:
        def enrich_public_oncokb_cache_for_sample(self, sample_id):
            assert sample_id == "sample-id"
            return {"queried": 12, "inserted": 3}

    monkeypatch.setattr(ingest, "_ensure_worker_runtime", lambda: None)
    monkeypatch.setattr(ingest, "task_family_enabled", lambda _family: True)
    monkeypatch.setattr(ingest, "get_internal_ingest_service", lambda: _Service())
    monkeypatch.setattr(ingest, "_record_ingest_audit", lambda *args, **kwargs: None)

    result = ingest.enrich_public_oncokb_cache_task.run(
        sample_id="sample-id", sample_name="SAMPLE_1"
    )

    assert result == {
        "status": "ok",
        "sample_id": "sample-id",
        "result": {"queried": 12, "inserted": 3},
    }
