from api.tasks import ingest


def test_resolve_sample_paths_maps_host_data_root_to_container_mount(tmp_path, monkeypatch):
    host_root = tmp_path / "host-data"
    manifest = host_root / "incoming" / "sample" / "coyote3.yaml"
    manifest.parent.mkdir(parents=True)
    manifest.write_text("name: SAMPLE_1\n", encoding="utf-8")

    monkeypatch.setenv("COYOTE3_DATA_HOST_ROOT", str(host_root))

    payload = ingest._resolve_relative_sample_paths(
        {
            "name": "SAMPLE_1",
            "vcf_files": str(host_root / "vcf" / "sample.vcf"),
            "files": {
                "cnv": {"path": str(host_root / "cnv" / "sample.cnv.json")},
                "cov": "relative/sample.cov.json",
            },
        },
        manifest,
    )

    assert payload["vcf_files"] == "/data/vcf/sample.vcf"
    assert payload["files"]["cnv"]["path"] == "/data/cnv/sample.cnv.json"
    assert payload["files"]["cov"] == "/data/incoming/sample/relative/sample.cov.json"


def test_ingest_watch_directory_once_renames_manifest_done(tmp_path, monkeypatch):
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

        def ingest_sample_bundle(self, payload, *, allow_update=False, increment=False):
            captured_payloads.append(
                {
                    "payload": payload,
                    "allow_update": allow_update,
                    "increment": increment,
                }
            )
            return {"sample_id": "sample-id", "sample_name": "SAMPLE_1"}

    monkeypatch.setenv("COYOTE3_INGEST_WATCH_DIR", str(watch_dir))
    monkeypatch.setenv("COYOTE3_INGEST_WATCH_UPDATE_EXISTING", "1")
    monkeypatch.setenv("COYOTE3_INGEST_WATCH_INCREMENT", "0")
    monkeypatch.setattr(ingest, "_ensure_worker_runtime", lambda: None)
    monkeypatch.setattr(ingest, "get_internal_ingest_service", lambda: _Service())
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
