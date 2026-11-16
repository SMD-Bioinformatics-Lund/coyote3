"""Explicit demo CLI settings are checked before importing or calling write integrations."""

from unittest.mock import Mock

import pytest
from coyote_demo import cli, host
from demo_test_support.deployment import demo_settings


@pytest.fixture
def settings(monkeypatch):
    for key, value in demo_settings().items():
        monkeypatch.setenv(key, str(value))


@pytest.mark.parametrize("apply", [False, True])
def test_cli_requires_explicit_apply_and_preserves_starter_selection(
    settings, monkeypatch, capsys, apply
):
    install = Mock(return_value={"status": "synthetic"})
    monkeypatch.setattr(host, "install_resources", install)
    cli.main(["--actor", "demo.admin", "--starter", *(["--apply"] if apply else [])])
    assert install.call_args.kwargs == {"actor": "demo.admin", "starter": True, "apply": apply}
    output = capsys.readouterr().out
    assert ("Plan only" in output) is (not apply)
    assert "synthetic" in output


@pytest.mark.parametrize(
    "arguments", [["--db", "ordinary"], ["--mongo-uri", "mongodb://remote.invalid:27017"]]
)
def test_cli_cannot_override_isolation_with_flags(settings, monkeypatch, arguments):
    install = Mock()
    monkeypatch.setattr(host, "install_resources", install)
    with pytest.raises(ValueError):
        cli.main(["--actor", "demo.admin", "--apply", *arguments])
    install.assert_not_called()


def test_cli_rejects_blank_actor_before_host_use(settings, monkeypatch):
    install = Mock()
    monkeypatch.setattr(host, "install_resources", install)
    with pytest.raises(ValueError, match="Actor"):
        cli.main(["--actor", " "])
    install.assert_not_called()
