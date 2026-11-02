"""Check analysis-server acknowledgements without uploading or modifying real samples."""

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from scripts.ingest import submit_ingest_manifest as client


@pytest.mark.parametrize("outcome", ["ok", "error", "interrupted"])
def test_streamed_server_logs_and_terminal_status(outcome, capsys):
    lines = [json.dumps({"event": "log", "level": "INFO", "message": "Parsing synthetic VCF"})]
    if outcome == "ok":
        lines.append(
            json.dumps({"event": "result", "data": {"status": "ok", "sample_id": "synthetic"}})
        )
    elif outcome == "error":
        lines.append(
            json.dumps({"event": "error", "status_code": 500, "data": {"error": "Parse failed"}})
        )
    lines.append("200")
    code = "import sys; sys.stdin.read(); print(" + repr("\n".join(lines)) + ", flush=True)"
    command = [sys.executable, "-c", code]
    if outcome == "interrupted":
        with pytest.raises(ValueError, match="without a terminal"):
            client.streamed_upload(command, "")
    else:
        result = client.streamed_upload(command, "")
        body, _, status = result.stdout.rpartition("\n")
        assert status == ("200" if outcome == "ok" else "500")
        assert json.loads(body) == (
            {"status": "ok", "sample_id": "synthetic"}
            if outcome == "ok"
            else {"error": "Parse failed"}
        )
    assert "Parsing synthetic VCF" in capsys.readouterr().err


@pytest.mark.parametrize("fail", [False, True])
def test_submission_lock_removed_after_exit(tmp_path, fail):
    path = tmp_path / "sample.yaml.submit.lock"
    try:
        with client.submission_lock(path):
            assert path.exists()
            with pytest.raises(ValueError, match="Another process"):
                with client.submission_lock(path):
                    pytest.fail("Concurrent submission acquired the lock")
            assert path.exists()
            if fail:
                raise RuntimeError("synthetic failure")
    except RuntimeError:
        assert fail
    assert not path.exists()
    with client.submission_lock(path):
        assert path.exists()
    assert not path.exists()


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
    with pytest.raises(ValueError, match="not a regular file"):
        client.submit_remote(remote_args)
    assert len(calls) == 1


def test_remote_rename_failure_recovers_without_another_upload(remote_args, monkeypatch):
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
    calls = []

    def upload(*a):
        calls.append(a)
        return {"status": "ok", "sample_id": "new", "message": "new upload"}

    monkeypatch.setattr(client, "upload", upload)
    assert client.submit_remote(remote_args) == 0
    assert len(calls) == 0


@pytest.mark.parametrize("source", ["argument", "file", "environment"])
def test_token_sources_never_enter_curl_arguments_or_receipts(args, tmp_path, monkeypatch, source):
    """The explicit credential sources share header validation and private stdin transport."""
    token = "synthetic-private-token"
    monkeypatch.setenv("API_BEARER_TOKEN", token)
    if source == "argument":
        args.token = token
    elif source == "file":
        path = tmp_path / "token.txt"
        path.write_text(token + "\n")
        args.token_file = str(path)
        monkeypatch.delenv("API_BEARER_TOKEN")

    def run(command, **kwargs):
        assert token not in str(command)
        assert "Bearer " + token in kwargs["input"]
        return SimpleNamespace(
            returncode=0, stdout='{"status":"ok","sample_id":"synthetic","message":"done"}\n200'
        )

    monkeypatch.setattr(client.subprocess, "run", run)
    assert client.submit(args) == 0
    assert token not in Path(args.yaml + ".ack.json").read_text()


@pytest.mark.parametrize("value", ["", "x\ny", "x\ry", 'x"y', "x\\y", "x" * 16385])
def test_unsafe_explicit_tokens_are_rejected_without_echoing_the_value(args, value):
    args.token = value
    with pytest.raises(ValueError, match="Supply a valid token") as error:
        client.load_token(args)
    if value:
        assert value not in str(error.value)


@pytest.mark.parametrize(
    "state,exit_code,suffix", [("SUCCESS", 0, ".done"), ("FAILURE", 1, ".failed")]
)
def test_async_acceptance_resumes_without_reupload_or_early_rename(
    args, monkeypatch, state, exit_code, suffix
):
    args.asynchronous = True
    uploads = Mock(return_value={"status": "accepted", "task_id": "synthetic-job"})
    monkeypatch.setattr(client, "upload", uploads)
    assert client.submit(args) == 0
    assert Path(args.yaml).exists()
    receipt_path = Path(args.yaml + ".ack.json")
    assert json.loads(receipt_path.read_text())["state"] == "accepted"
    args.wait = True
    statuses = iter(
        [
            {"state": "STARTED"},
            {
                "state": state,
                "result": {"sample_id": "synthetic", "sample_name": "synthetic"},
                "error": "Synthetic rejection",
            },
        ]
    )
    monkeypatch.setattr(client, "fetch_job_status", lambda *a, **kw: next(statuses))
    monkeypatch.setattr(client.time, "sleep", lambda _: None)
    assert client.submit(args) == exit_code
    assert uploads.call_count == 1
    assert Path(args.yaml + suffix).exists()
    assert not Path(args.yaml).exists()
    receipt = json.loads(receipt_path.read_text())
    assert receipt["state"] == "terminal"
    assert receipt["task_id"] == "synthetic-job"


def test_async_wait_interruption_keeps_accepted_receipt_for_resume(args, monkeypatch):
    args.asynchronous = True
    args.wait = True
    upload = Mock(return_value={"status": "accepted", "task_id": "synthetic-job"})
    monkeypatch.setattr(client, "upload", upload)

    def interrupted(*a, **kw):
        raise ValueError("Connection interrupted")

    monkeypatch.setattr(client, "fetch_job_status", interrupted)
    with pytest.raises(ValueError, match="Connection interrupted"):
        client.submit(args)
    assert Path(args.yaml).exists()
    assert json.loads(Path(args.yaml + ".ack.json").read_text())["state"] == "accepted"
    monkeypatch.setattr(
        client,
        "fetch_job_status",
        lambda *a, **kw: {"state": "SUCCESS", "result": {"sample_id": "synthetic"}},
    )
    assert client.submit(args) == 0
    assert upload.call_count == 1


def test_async_upload_uses_the_existing_endpoint_and_private_bearer_header(args, monkeypatch):
    args.asynchronous = True

    def run(command, **kwargs):
        assert command[-1].endswith("/sample-bundle/upload/async")
        assert "synthetic-token" not in str(command)
        return SimpleNamespace(
            returncode=0, stdout='{"status":"accepted","task_id":"synthetic-job"}\n202'
        )

    monkeypatch.setattr(client.subprocess, "run", run)
    assert client.upload(args, Path(args.yaml), "synthetic-token")["status"] == "accepted"


def test_async_wait_timeout_retains_job_and_does_not_rename(args, monkeypatch):
    args.asynchronous = True
    args.wait = True
    args.wait_timeout = 1
    monkeypatch.setattr(
        client, "upload", lambda *a: {"status": "accepted", "task_id": "synthetic-job"}
    )
    monkeypatch.setattr(client, "fetch_job_status", lambda *a, **kw: {"state": "STARTED"})
    clock = iter([0, 0, 1, 2])
    monkeypatch.setattr(
        client, "time", SimpleNamespace(monotonic=lambda: next(clock), sleep=lambda _: None)
    )
    with pytest.raises(ValueError, match="Wait timed out"):
        client.submit(args)
    assert Path(args.yaml).exists()
    assert (
        json.loads(Path(args.yaml + ".ack.json").read_text())["acknowledgement"]["task_id"]
        == "synthetic-job"
    )


@pytest.mark.parametrize("failure", [None, "wrong_id", "unauthorized", "invalid_json"])
def test_job_polling_preserves_prefix_and_does_not_leak_secrets(args, monkeypatch, failure):
    response = {
        "status": "ok",
        "task_id": "synthetic-job",
        "state": "SUCCESS",
        "ready": True,
        "successful": True,
        "result": {"sample_id": "synthetic"},
    }
    if failure == "wrong_id":
        response["task_id"] = "other-job"

    def run(command, **kwargs):
        assert command[-1] == "https://example.test/coyote3_dev/api/v1/internal/tasks/synthetic-job"
        assert "synthetic-secret" not in str(command)
        assert "Bearer synthetic-secret" in kwargs["input"]
        body = "not json" if failure == "invalid_json" else json.dumps(response)
        return SimpleNamespace(
            returncode=0, stdout=body + ("\n401" if failure == "unauthorized" else "\n200")
        )

    monkeypatch.setattr(client.subprocess, "run", run)
    if failure:
        with pytest.raises(ValueError) as error:
            client.fetch_job_status(args, "synthetic-job", "synthetic-secret", timeout=5)
        assert "synthetic-secret" not in str(error.value)
    else:
        assert (
            client.fetch_job_status(args, "synthetic-job", "synthetic-secret", timeout=5)["ready"]
            is True
        )


def test_changed_remote_manifest_is_left_in_place(remote_args, monkeypatch):
    def upload(*a):
        Path(remote_args.yaml).write_text("name: changed\n")
        return {"status": "ok", "sample_id": "synthetic", "message": "done"}

    monkeypatch.setattr(client, "upload", upload)
    with pytest.raises(ValueError, match="Remote YAML changed"):
        client.submit_remote(remote_args)
    assert Path(remote_args.yaml).read_text() == "name: changed\n"
    assert not Path(remote_args.yaml + ".done").exists()


def test_remote_existing_marker_does_not_block_submission(remote_args, monkeypatch):
    Path(remote_args.yaml + ".failed").write_text("previous")
    monkeypatch.setattr(client, "upload", lambda *a: {"status": "failed", "message": "new failure"})
    assert client.submit_remote(remote_args) == 1
    assert (
        list(Path(remote_args.yaml).parent.glob("remote.yaml.history.*/remote.yaml.failed"))[
            0
        ].read_text()
        == "previous"
    )


def test_unconfirmed_remote_upload_never_renames_source(remote_args, monkeypatch):
    def fail(*a):
        raise ValueError("Unconfirmed timeout")

    monkeypatch.setattr(client, "upload", fail)
    with pytest.raises(ValueError, match="Unconfirmed timeout"):
        client.submit_remote(remote_args)
    assert Path(remote_args.yaml).exists()
    receipts = list(Path(remote_args.state_dir).glob("*.ack.json"))
    assert len(receipts) == 1
    assert json.loads(receipts[0].read_text())["state"] == "pending"


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
        token=None,
        token_file=None,
        asynchronous=False,
        wait=False,
        wait_timeout=60,
        poll_interval=0.01,
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
    assert json.loads(Path(args.yaml + ".ack.json").read_text())["state"] == "pending"


def test_http_error_displays_server_reason_without_finalizing(args, monkeypatch):
    monkeypatch.setattr(
        client.subprocess,
        "run",
        lambda *a, **kw: SimpleNamespace(
            returncode=0,
            stdout='{"error":"Ingest failed","hint":"Check translocation annotations","request_id":"synthetic-request"}\n500',
        ),
    )
    with pytest.raises(
        ValueError, match="Ingest failed.*Check translocation annotations.*synthetic-request"
    ):
        client.submit(args)
    assert Path(args.yaml).exists()


def test_saved_receipt_finishes_rename_without_resubmission(args, monkeypatch):
    manifest = Path(args.yaml)
    client.save_receipt(
        Path(args.yaml + ".ack.json"),
        {
            "sha256": client.fingerprint(manifest),
            "base_url": args.base_url,
            "options": client.submission_options(args),
            "archive_sha256": None,
            "state": "terminal",
            "acknowledgement": {"status": "ok", "sample_id": "synthetic", "message": "done"},
        },
    )
    calls = []

    def upload(*a):
        calls.append(a)
        return {"status": "ok", "sample_id": "new", "message": "new upload"}

    monkeypatch.setattr(client, "upload", upload)
    assert client.submit(args) == 0
    assert len(calls) == 0


@pytest.mark.parametrize(
    "options", [None, {"increment": False, "update_existing": False, "archive": None}]
)
def test_changed_increment_or_old_receipt_blocks_resubmission(args, monkeypatch, options):
    manifest = Path(args.yaml)
    args.increment = True
    client.save_receipt(
        Path(args.yaml + ".ack.json"),
        {
            "sha256": client.fingerprint(manifest),
            "base_url": args.base_url,
            "options": options,
            "acknowledgement": {"status": "failed", "message": "Sample already exists"},
        },
    )

    def upload(options, *unused):
        assert options.increment is True
        return {"status": "ok", "sample_id": "new", "message": "incremented"}

    monkeypatch.setattr(client, "upload", upload)
    with pytest.raises(ValueError, match="reconcile"):
        client.submit(args)
    assert manifest.exists()
    assert not Path(args.yaml + ".failed").exists()


@pytest.mark.parametrize("remote", [False, True])
@pytest.mark.parametrize("failure", [ValueError, KeyboardInterrupt])
def test_uncertain_or_interrupted_upload_blocks_next_cron_run(
    remote_args, monkeypatch, remote, failure
):
    """Timeouts and abrupt interruption cannot trigger another incremented submission."""
    remote_args.increment = True
    calls = []

    def upload(*unused):
        calls.append(True)
        raise failure("Connection lost after commit")

    monkeypatch.setattr(client, "upload", upload)
    submit = client.submit_remote if remote else client.submit
    with pytest.raises(failure):
        submit(remote_args)
    with pytest.raises(ValueError, match="outcome is unconfirmed"):
        submit(remote_args)
    assert len(calls) == 1
    assert Path(remote_args.yaml).exists()


def test_local_rename_failure_recovers_without_another_upload(args, monkeypatch):
    """A durable successful response survives inability to rename the manifest."""
    link = client.os.link
    calls = []

    def upload(*unused):
        calls.append(True)
        return {"status": "ok", "sample_id": "synthetic", "message": "done"}

    def denied(*unused):
        raise PermissionError("Read-only source")

    monkeypatch.setattr(client, "upload", upload)
    monkeypatch.setattr(client.os, "link", denied)
    with pytest.raises(PermissionError):
        client.submit(args)
    monkeypatch.setattr(client.os, "link", link)
    assert client.submit(args) == 0
    assert len(calls) == 1


def test_changed_archive_cannot_reuse_a_saved_result(args, monkeypatch):
    """The ZIP contents participate in receipt identity even at the same file path."""
    archive = Path(args.yaml).with_suffix(".zip")
    archive.write_bytes(b"synthetic first archive")
    args.archive = str(archive)
    monkeypatch.setattr(
        client, "upload", lambda *a: {"status": "ok", "sample_id": "synthetic", "message": "done"}
    )
    client.submit(args)
    Path(args.yaml + ".done").rename(args.yaml)
    archive.write_bytes(b"synthetic second archive")
    with pytest.raises(ValueError, match="differs"):
        client.submit(args)


def test_journal_write_failure_prevents_upload(args, monkeypatch):
    """No request is sent unless durable pending state can be recorded first."""

    def denied(*unused):
        raise OSError("State storage unavailable")

    monkeypatch.setattr(client, "save_receipt", denied)
    monkeypatch.setattr(client, "upload", lambda *a: pytest.fail("Must not upload"))
    with pytest.raises(OSError, match="State storage unavailable"):
        client.submit(args)
    assert Path(args.yaml).exists()


def test_existing_marker_is_archived_on_submission(args, monkeypatch):
    destination = Path(args.yaml + ".done")
    destination.write_text("prior result")
    monkeypatch.setattr(
        client, "upload", lambda *a: {"status": "ok", "sample_id": "new", "message": "done"}
    )
    assert client.submit(args) == 0
    assert list(destination.parent.glob("*.history.*/*.done"))[0].read_text() == "prior result"


def test_changed_manifest_is_not_marked_done(args, monkeypatch):
    def upload(*unused):
        Path(args.yaml).write_text("name: changed\n")
        return {"status": "ok", "sample_id": "synthetic", "message": "done"}

    monkeypatch.setattr(client, "upload", upload)
    with pytest.raises(ValueError, match="changed during submission"):
        client.submit(args)
    assert Path(args.yaml).exists()


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
