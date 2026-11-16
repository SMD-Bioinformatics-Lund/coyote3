"""Fast standalone resource and disabled-extension checks."""

import json

import pytest
from coyote_demo.api import routers
from coyote_demo.cli import main
from coyote_demo.resources import DEMO_CENTER, GROUPS_PATH, WORKFLOW_BUNDLE


def test_package_contains_synthetic_resources():
    assert (WORKFLOW_BUNDLE / "starter/first_sample.yaml").is_file()
    assert (WORKFLOW_BUNDLE / "starter/rna_fusion.yaml").is_file()
    assert len(list((WORKFLOW_BUNDLE / "manifests").glob("*.yaml"))) == 18
    assert json.loads((DEMO_CENTER / "clinical_rule_sets.json").read_text())
    assert {json.loads(line)["group_id"] for line in GROUPS_PATH.read_text().splitlines()} == {
        "hematology",
        "myeloid",
        "lymphoid",
        "solid",
        "pgx",
    }


def test_installed_extension_is_inactive_without_explicit_enablement(monkeypatch):
    monkeypatch.delenv("COYOTE_DEMO_ENABLED", raising=False)
    assert routers() is None


def test_cli_help_does_not_require_host_configuration(capsys):
    with pytest.raises(SystemExit) as result:
        main(["--help"])
    assert result.value.code == 0
    assert "--starter" in capsys.readouterr().out
