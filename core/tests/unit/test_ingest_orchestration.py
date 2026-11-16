"""Durable ingestion and manifest orchestration using only explicit core ports."""

from unittest.mock import Mock

import pytest
from coyote.application.ingest.messages import ingest_task_name
from coyote.application.ingest.watcher import ManifestWatcher, ManifestWatchSettings
from coyote.application.ingest.worker import IngestJobRunner


@pytest.fixture
def runner_ports():
    """Bind an in-memory lease and callbacks without a transport or database driver."""
    job = {
        "kind": "sample_bundle",
        "state": "running",
        "lease_token": "claim-token",
        "attempts": 1,
        "source_payload": {},
        "submitted_by": "synthetic-user",
        "staging_dir": "synthetic-staging",
    }
    repository = Mock()
    repository.get.return_value = job
    repository.claim.return_value = job
    repository.fail.return_value = True
    ports = {
        "repository": repository,
        "execute": Mock(return_value={"status": "ok"}),
        "family_enabled": Mock(return_value=True),
        "retryable_error": Mock(return_value=False),
        "audit": Mock(),
        "notify_failure": Mock(),
        "cleanup_staging": Mock(),
        "lease_seconds": 90,
    }
    return ports


def test_job_completion_uses_executor_transaction(runner_ports):
    transaction = object()
    result = {"status": "ok", "sample_id": "synthetic"}

    def execute(job, *, record_completion):
        assert job["lease_token"] == "claim-token"
        record_completion(result, transaction)
        return result

    runner_ports["execute"] = execute
    assert IngestJobRunner(**runner_ports).run("job") == result
    runner_ports["repository"].complete.assert_called_once_with(
        "job", "claim-token", result, transaction
    )
    runner_ports["cleanup_staging"].assert_called_once_with("synthetic-staging")


@pytest.mark.parametrize("reason", ["disabled", "busy", "succeeded", "failed", "missing"])
def test_nonexecuting_job_outcomes_do_not_invoke_executor(runner_ports, reason):
    repository = runner_ports["repository"]
    if reason == "disabled":
        runner_ports["family_enabled"].return_value = False
    elif reason == "busy":
        repository.claim.return_value = None
    elif reason == "missing":
        repository.get.return_value = None
    else:
        repository.get.return_value = {
            "kind": "sample_bundle",
            "state": reason,
            "result": {"status": "ok", "written": 1},
            "error": "permanent failure",
        }
    runner = IngestJobRunner(**runner_ports)
    if reason in {"failed", "missing"}:
        with pytest.raises(ValueError):
            runner.run("job")
    else:
        result = runner.run("job")
        assert result["status"] == ("ok" if reason == "succeeded" else reason)
    runner_ports["execute"].assert_not_called()


@pytest.mark.parametrize("retryable", [False, True])
def test_execution_failure_retains_staging_and_notifies_only_permanent_failure(
    runner_ports, retryable
):
    runner_ports["retryable_error"].return_value = retryable
    runner_ports["execute"].side_effect = ValueError("synthetic input is invalid")
    with pytest.raises(ValueError, match="synthetic input"):
        IngestJobRunner(**runner_ports).run("job")
    runner_ports["cleanup_staging"].assert_not_called()
    assert runner_ports["repository"].fail.call_args.kwargs["retryable"] is retryable
    assert runner_ports["notify_failure"].call_count == (0 if retryable else 1)


def test_committed_result_wins_over_transport_failure(runner_ports):
    result = {"status": "ok", "written": 1}
    repository = runner_ports["repository"]
    repository.get.side_effect = [
        repository.get.return_value,
        {"state": "succeeded", "result": result},
    ]
    runner_ports["execute"].side_effect = RuntimeError("connection lost after commit")
    assert IngestJobRunner(**runner_ports).run("job") == result
    runner_ports["notify_failure"].assert_not_called()
    runner_ports["cleanup_staging"].assert_called_once()


def test_lost_claim_cannot_remove_staging_or_notify_failure(runner_ports):
    runner_ports["execute"].side_effect = RuntimeError("lease replaced during execution")
    runner_ports["repository"].fail.return_value = False
    assert IngestJobRunner(**runner_ports).run("job") == {"status": "busy", "job_id": "job"}
    runner_ports["cleanup_staging"].assert_not_called()
    runner_ports["notify_failure"].assert_not_called()
    assert [call.args[0] for call in runner_ports["audit"].call_args_list] == [
        "ingest.bundle.started"
    ]


@pytest.mark.parametrize("outcome", ["busy", "disabled", "ok", "temporary", "invalid"])
def test_watcher_acknowledges_only_completed_stable_inputs(tmp_path, outcome):
    manifest = tmp_path / "coyote4.yaml"
    manifest.write_text("name: SYNTHETIC\n")
    execute = Mock(return_value={"status": outcome, "sample_id": "synthetic"})
    if outcome in {"temporary", "invalid"}:
        execute.side_effect = ValueError("synthetic failure")
    submit = Mock(return_value="unused")
    watcher = ManifestWatcher(
        settings=ManifestWatchSettings(
            directory=tmp_path,
            manifest_name="coyote4.yaml",
            done_suffix=".done",
            failed_suffix=".failed",
            update_existing=False,
            increment=False,
        ),
        parse_payload=Mock(return_value={"name": "SYNTHETIC"}),
        submit_job=submit,
        execute_job=execute,
        retryable_error=lambda error: outcome == "temporary",
        audit=Mock(),
    )
    result = watcher.scan(task_id="scan")
    identity = submit.call_args.kwargs["job_id"]
    execute.assert_called_once_with(identity)
    assert submit.call_args.kwargs["submitted_by"] == "ingest-watcher"
    assert result["scanned"] == 1
    assert manifest.exists() is (outcome in {"busy", "disabled", "temporary"})
    assert manifest.with_name("coyote4.yaml.done").exists() is (outcome == "ok")
    assert manifest.with_name("coyote4.yaml.failed").exists() is (outcome == "invalid")


def test_message_contract_rejects_unknown_jobs():
    assert ingest_task_name("sample_bundle") == "coyote_relay.tasks.ingest_sample_bundle"
    with pytest.raises(KeyError):
        ingest_task_name("execute_arbitrary_code")
