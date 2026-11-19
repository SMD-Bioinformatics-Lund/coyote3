"""Installed ingestion command entry points parse help without contacting services."""

import sys

import pytest

from coyote_relay import login, submit, validate


@pytest.mark.parametrize("command", [login, submit, validate])
def test_console_entry_point_accepts_process_arguments(command, monkeypatch, capsys):
    monkeypatch.setattr(sys, "argv", ["coyote-relay", "--help"])

    with pytest.raises(SystemExit) as result:
        command.main()

    assert result.value.code == 0
    assert "usage:" in capsys.readouterr().out
