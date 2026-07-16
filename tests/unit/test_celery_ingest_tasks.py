from api.tasks import ingest


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
