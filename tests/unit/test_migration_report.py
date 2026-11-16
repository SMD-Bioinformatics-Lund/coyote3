"""Migration CLI reporting preserves output files and failure exit statuses."""

import json
from datetime import datetime, timezone

import pytest

from scripts.database.migration_report import run_migration_command


@pytest.mark.parametrize("save_report", [False, True])
def test_migration_report_matches_stdout_with_optional_file(tmp_path, capsys, save_report):
    """Successful commands serialize dates consistently and terminate files with a newline."""
    path = tmp_path / "results" / "migration.json" if save_report else None
    report = {"mode": "dry-run", "checked_on": datetime(2026, 1, 1, tzinfo=timezone.utc)}
    assert run_migration_command(lambda: report, report_path=path) == 0
    output = capsys.readouterr()
    assert json.loads(output.out) == {"mode": "dry-run", "checked_on": "2026-01-01 00:00:00+00:00"}
    assert output.err == ""
    if path is not None:
        assert path.read_text() == output.out
        assert path.read_text().endswith("\n")


@pytest.mark.parametrize("error_type", [RuntimeError, ValueError])
def test_failed_operation_does_not_replace_a_previous_report(tmp_path, capsys, error_type):
    """A rejected operation reports its error without overwriting successful evidence."""
    path = tmp_path / "report.json"
    path.write_text('{"previous": true}\n')

    def fail():
        raise error_type("source and target overlap")

    assert run_migration_command(fail, report_path=path) == 2
    output = capsys.readouterr()
    assert output.out == ""
    assert output.err == "ERROR: source and target overlap\n"
    assert path.read_text() == '{"previous": true}\n'
