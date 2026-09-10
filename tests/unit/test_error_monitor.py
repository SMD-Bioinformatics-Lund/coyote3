"""Calendar rollover, durable error delivery, and service routing regressions."""

import gzip
import json
import logging
from datetime import datetime, timezone

from api.infra.observability.error_monitor import DiskErrorMonitor, parse_syslog
from api.infra.observability.logging import DailyServiceFileHandler, JsonFormatter


def test_logs_change_date_at_local_midnight_and_keep_services_separate(tmp_path):
    handler = DailyServiceFileHandler(tmp_path, "Europe/Stockholm")
    handler.setFormatter(JsonFormatter())
    for service in ("api", "worker", "beat", "ui"):
        for hour, minute in ((21, 59), (22, 0)):
            record = logging.makeLogRecord({"msg": "diagnostic", "service": service})
            record.created = datetime(2026, 9, 9, hour, minute, tzinfo=timezone.utc).timestamp()
            handler.handle(record)
        assert (tmp_path / f"2026/09/09/{service}_2026-09-09.log").exists()
        assert (tmp_path / f"2026/09/10/{service}_2026-09-10.log").exists()


def test_monitor_retries_with_snapshot_and_does_not_repeat_successful_recipients(tmp_path):
    source = tmp_path / "2026/09/09/api_2026-09-09.log"
    source.parent.mkdir(parents=True)
    content = json.dumps({"severity": "error", "message": "database unavailable"}) + "\n"
    source.write_text(content)
    monitor = DiskErrorMonitor(tmp_path)
    monitor.scan()
    calls = []

    def sender(**message):
        calls.append(message)
        return message["to_email"] == "first@example.test"

    assert monitor.deliver([], sender) == 0
    assert monitor.deliver(["first@example.test", "second@example.test"], sender) == 0
    attachment = calls[0]["attachments"][0]
    assert attachment[0] == "api_2026-09-09.log.gz"
    assert gzip.decompress(attachment[1]).decode() == content
    assert "database unavailable" in calls[0]["text_body"]
    source.unlink()  # Delivery still works after source retention.
    restarted = DiskErrorMonitor(tmp_path)
    remaining = []
    assert (
        restarted.deliver(
            ["first@example.test", "second@example.test"],
            lambda **message: remaining.append(message) or True,
        )
        == 1
    )
    assert [message["to_email"] for message in remaining] == ["second@example.test"]
    assert restarted.deliver(["first@example.test"], sender) == 0


def test_monitor_reads_compressed_logs_and_waits_for_complete_lines(tmp_path):
    source = tmp_path / "2026/09/09/beat_2026-09-09.log"
    source.parent.mkdir(parents=True)
    record = json.dumps({"severity": "critical", "message": "scheduler stopped"})
    source.write_text(record)
    monitor = DiskErrorMonitor(tmp_path)
    monitor.scan()
    assert monitor.offsets == {}
    with gzip.open(str(source) + ".gz", "wt") as stream:
        stream.write(record + "\n")
    source.unlink()
    monitor.scan()
    calls = []
    assert (
        monitor.deliver(["monitor@example.test"], lambda **message: calls.append(message) or True)
        == 1
    )
    monitor.scan()
    assert monitor.deliver(["monitor@example.test"], lambda **message: False) == 0


def test_internal_syslog_routes_errors_and_rejects_unknown_services():
    record = parse_syslog("<187>Sep 9 12:00:00 nginx ui: upstream failed")
    assert record.service == "ui"
    assert record.levelno == logging.ERROR
    assert parse_syslog("<187>host arbitrary: message") is None
    assert parse_syslog('<190>host proxy: client "GET / HTTP/1.1" 502 12').levelno == logging.ERROR


def test_service_wrapper_records_startup_failures_and_exit_status(tmp_path):
    import os
    import subprocess
    import sys

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "api.infra.observability.run_service",
            "worker",
            sys.executable,
            "-c",
            "raise RuntimeError('synthetic startup failure')",
        ],
        env={**os.environ, "LOG_ROOT": str(tmp_path), "LOCAL_TIME_ZONE": "UTC"},
        capture_output=True,
        timeout=10,
    )
    assert result.returncode == 1
    records = [
        json.loads(line)
        for path in tmp_path.glob("*/*/*/*.log")
        for line in path.read_text().splitlines()
    ]
    assert all(record["service"] == "worker" for record in records)
    assert any("synthetic startup failure" in record["message"] for record in records)
    assert records[-1]["severity"] == "error"


def test_wrapper_preserves_ui_diagnostics_and_tracebacks():
    from api.infra.observability.run_service import output_record

    record = output_record(
        json.dumps(
            {
                "logger": "coyote.ui",
                "service": "ui",
                "severity": "error",
                "message": "render failed",
                "exception": "synthetic stack",
            }
        ),
        "api",
    )
    assert record.service == "ui"
    assert json.loads(JsonFormatter().format(record))["exception"] == "synthetic stack"
