"""Check analysis-server acknowledgements without uploading or modifying real samples."""

import argparse
import json
import shutil
import subprocess
from pathlib import Path
from types import SimpleNamespace

import pytest

from scripts import submit_ingest_manifest as client


@pytest.fixture
def remote_args(args, tmp_path, monkeypatch):
    manifest = tmp_path / "remote.yaml"
    manifest.write_text("name: synthetic\n")
    args.yaml = str(manifest)
    args.remote_host = "synthetic@analysis.example.test"
    args.ssh_port = 22
    args.identity_file = None
    args.state_dir = str(tmp_path / "receipts")

    def shell(_args, script, *parameters):
        result = subprocess.run(
            ["sh", "-s", "--", *parameters],
            input=script,
            text=True,
            capture_output=True,
            check=False,
        )
        if result.returncode:
            raise ValueError(result.stderr)

    monkeypatch.setattr(client, "remote_command", shell)
    monkeypatch.setattr(
        client, "fetch_remote", lambda _args, source, target: shutil.copyfile(source, target)
    )
    return args


@pytest.mark.parametrize("status,suffix,code", [("ok", ".done", 0), ("failed", ".failed", 1)])
def test_remote_acknowledgement_moves_original_and_is_idempotent(
    remote_args, monkeypatch, status, suffix, code
):
    calls = []

    def upload(args, manifest, token):
        calls.append(manifest)
        assert manifest != Path(remote_args.yaml)
        return {"status": status, "sample_id": "synthetic", "message": "Specific reason"}

    monkeypatch.setattr(client, "upload", upload)
    assert client.submit_remote(remote_args) == code
    assert Path(remote_args.yaml + suffix).read_text() == "name: synthetic\n"
    assert not Path(remote_args.yaml).exists()
    assert client.submit_remote(remote_args) == code
    assert len(calls) == 1


def test_remote_rename_failure_reuses_receipt_without_upload(remote_args, monkeypatch):
    finalize = client.finalize_remote
    monkeypatch.setattr(
        client, "upload", lambda *a: {"status": "ok", "sample_id": "synthetic", "message": "done"}
    )

    def fail(*a):
        raise ValueError("SSH unavailable")

    monkeypatch.setattr(client, "finalize_remote", fail)
    with pytest.raises(ValueError, match="SSH unavailable"):
        client.submit_remote(remote_args)
    assert Path(remote_args.yaml).exists()
    assert len(list(Path(remote_args.state_dir).glob("*.ack.json"))) == 1
    monkeypatch.setattr(client, "finalize_remote", finalize)
    monkeypatch.setattr(client, "upload", lambda *a: pytest.fail("Must not upload twice"))
    assert client.submit_remote(remote_args) == 0


def test_changed_remote_manifest_is_left_in_place(remote_args, monkeypatch):
    def upload(*a):
        Path(remote_args.yaml).write_text("name: changed\n")
        return {"status": "ok", "sample_id": "synthetic", "message": "done"}

    monkeypatch.setattr(client, "upload", upload)
    with pytest.raises(ValueError, match="Remote YAML changed"):
        client.submit_remote(remote_args)
    assert Path(remote_args.yaml).read_text() == "name: changed\n"
    assert not Path(remote_args.yaml + ".done").exists()


def test_remote_existing_marker_blocks_submission(remote_args, monkeypatch):
    Path(remote_args.yaml + ".failed").write_text("previous")
    monkeypatch.setattr(client, "upload", lambda *a: pytest.fail("Must not upload"))
    with pytest.raises(ValueError, match="marker already exists"):
        client.submit_remote(remote_args)


def test_unconfirmed_remote_upload_never_renames_source(remote_args, monkeypatch):
    def fail(*a):
        raise ValueError("Unconfirmed timeout")

    monkeypatch.setattr(client, "upload", fail)
    with pytest.raises(ValueError, match="Unconfirmed timeout"):
        client.submit_remote(remote_args)
    assert Path(remote_args.yaml).exists()
    assert not list(Path(remote_args.state_dir).glob("*.ack.json"))


def test_remote_shell_metacharacters_rejected_before_connecting(remote_args, monkeypatch):
    remote_args.yaml = "/synthetic/$(touch injected).yaml"
    monkeypatch.setattr(client, "remote_command", lambda *a: pytest.fail("Must not connect"))
    with pytest.raises(ValueError, match="literal"):
        client.submit_remote(remote_args)


@pytest.fixture
def args(tmp_path, monkeypatch):
    manifest = tmp_path / "synthetic sample.yaml"
    manifest.write_text("name: synthetic\n")
    monkeypatch.setenv("API_BEARER_TOKEN", "synthetic-token")
    return argparse.Namespace(
        yaml=str(manifest),
        base_url="https://example.test/coyote3_dev",
        auth="bearer",
        archive=None,
        timeout=60,
        ca_bundle=None,
        update_existing=False,
        increment=False,
    )


@pytest.mark.parametrize("status,suffix,code", [("ok", ".done", 0), ("failed", ".failed", 1)])
def test_terminal_acknowledgement_moves_manifest_and_preserves_reason(
    args, monkeypatch, status, suffix, code
):
    acknowledgement = {"status": status, "sample_id": "synthetic", "message": "Specific result"}
    monkeypatch.setattr(client, "upload", lambda *a: acknowledgement)
    original = Path(args.yaml).read_bytes()
    assert client.submit(args) == code
    assert not Path(args.yaml).exists()
    assert Path(args.yaml + suffix).read_bytes() == original
    assert (
        json.loads(Path(args.yaml + ".ack.json").read_text())["acknowledgement"] == acknowledgement
    )
    assert Path(args.yaml + ".ack.json").stat().st_mode & 0o777 == 0o600


@pytest.mark.parametrize(
    "returncode,body",
    [
        (28, "\n000"),
        (0, '{"detail":"Unauthorized"}\n401'),
        (0, "<html>Bad gateway</html>\n502"),
        (0, "not json\n200"),
        (0, '{"status":"accepted"}\n200'),
        (0, '{"status":"ok","message":"ok"}\n200'),
    ],
)
def test_unconfirmed_upload_leaves_manifest_unchanged(args, monkeypatch, returncode, body):
    monkeypatch.setattr(
        client.subprocess,
        "run",
        lambda *a, **kw: SimpleNamespace(returncode=returncode, stdout=body),
    )
    with pytest.raises(ValueError):
        client.submit(args)
    assert Path(args.yaml).exists()
    assert not Path(args.yaml + ".done").exists()
    assert not Path(args.yaml + ".failed").exists()
    assert not Path(args.yaml + ".ack.json").exists()


def test_saved_receipt_finishes_without_resubmitting(args, monkeypatch):
    manifest = Path(args.yaml)
    client.save_receipt(
        Path(args.yaml + ".ack.json"),
        {
            "sha256": client.fingerprint(manifest),
            "base_url": args.base_url,
            "acknowledgement": {"status": "ok", "sample_id": "synthetic", "message": "done"},
        },
    )
    monkeypatch.setattr(
        client, "upload", lambda *a: pytest.fail("Must not resubmit acknowledged input")
    )
    assert client.submit(args) == 0


def test_existing_marker_is_not_overwritten_or_submitted(args, monkeypatch):
    destination = Path(args.yaml + ".done")
    destination.write_text("prior result")
    monkeypatch.setattr(client, "upload", lambda *a: pytest.fail("Must not upload"))
    with pytest.raises(ValueError, match="already exists"):
        client.submit(args)
    assert destination.read_text() == "prior result"


def test_changed_manifest_is_not_marked_done(args, monkeypatch):
    def upload(*unused):
        Path(args.yaml).write_text("name: changed\n")
        return {"status": "ok", "sample_id": "synthetic", "message": "done"}

    monkeypatch.setattr(client, "upload", upload)
    with pytest.raises(ValueError, match="changed during submission"):
        client.submit(args)
    assert Path(args.yaml).exists()
    with pytest.raises(ValueError, match="different input"):
        client.submit(args)


@pytest.mark.parametrize("auth", ["internal", "bearer", "ingest"])
def test_upload_streams_files_and_keeps_token_out_of_arguments(args, monkeypatch, tmp_path, auth):
    args.auth = auth
    monkeypatch.setenv("INTERNAL_API_TOKEN", "synthetic-token")
    monkeypatch.setenv("COYOTE3_INGEST_TOKEN", "synthetic-token")
    args.archive = str(tmp_path / 'sample,"data".zip')
    Path(args.archive).write_bytes(b"synthetic")

    def run(command, **kwargs):
        assert "synthetic-token" not in " ".join(command)
        header = (
            "X-Coyote-Internal-Token: synthetic-token"
            if auth == "internal"
            else "Authorization: Bearer synthetic-token"
        )
        if auth == "ingest":
            header = "X-Coyote-Ingest-Token: synthetic-token"
        assert header in kwargs["input"]
        assert (
            command[-1]
            == "https://example.test/coyote3_dev/api/v1/internal/ingest/sample-bundle/upload"
        )
        assert "acknowledge=true" in command
        assert client.form_file("data_archive", Path(args.archive), "application/zip") in command
        return SimpleNamespace(
            returncode=0, stdout='{"status":"ok","sample_id":"synthetic","message":"done"}\n200'
        )

    monkeypatch.setattr(client.subprocess, "run", run)
    assert client.submit(args) == 0
