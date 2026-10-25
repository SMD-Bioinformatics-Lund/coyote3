"""Library imports and explicit center startup preserve configuration ownership."""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from coyote3.config import CenterConfiguration


def run_python(code, **environment):
    """Run a fresh process so immutable center contracts cannot leak between tests."""
    return subprocess.run(
        [sys.executable, "-c", code],
        env={**os.environ, **environment},
        text=True,
        capture_output=True,
        check=True,
    )


def test_library_import_ignores_deployment_discovery(tmp_path):
    result = run_python(
        "import sys; from coyote3.application.operations import CoyoteApplication; "
        "from coyote3_client import CoyoteClient; "
        "assert not any(n == 'api' or n.startswith('api.') for n in sys.modules); "
        "assert 'dotenv' not in sys.modules; print('ok')",
        COYOTE3_CENTER_CONFIG_DIR=str(tmp_path / "missing"),
        AUTHENTICATION_PROVIDERS="unsupported",
    )
    assert result.stdout.strip() == "ok"


def test_host_binds_explicit_configuration_before_contract_imports():
    directory = str(Path("config/examples/center").resolve())
    result = run_python(
        "from pathlib import Path; "
        "from coyote3.config import CenterConfiguration, configure_center; "
        f"configure_center(CenterConfiguration(directory=Path({directory!r}), "
        "authentication_providers='local')); "
        "from coyote3.config.constants import AUTH_TYPE_OPTIONS; "
        "assert AUTH_TYPE_OPTIONS == ('local',); "
        "from coyote3.application.operations import CoyoteApplication; print('ok')",
    )
    assert result.stdout.strip() == "ok"


def test_library_rejects_switching_center_after_contracts_are_initialized():
    result = run_python(
        "from coyote3.config.constants import AUTH_TYPE_OPTIONS\n"
        "from coyote3.config import CenterConfiguration, configure_center\n"
        "try:\n"
        " configure_center(CenterConfiguration(authentication_providers='local'))\n"
        "except RuntimeError:\n"
        " print('rejected')\n"
        "else:\n"
        " raise AssertionError('Late profile selection changed existing contracts')\n",
    )
    assert result.stdout.strip() == "rejected"


def test_center_manifest_must_use_the_loader_supported_format(tmp_path):
    for name in ("contact.toml", "clinical_vocabulary.toml", "filter_flag_metadata.yaml"):
        (tmp_path / name).write_text("")
    (tmp_path / "manifest.json").write_text(json.dumps({"format": 999}))
    with pytest.raises(ValueError, match="Unsupported center configuration format"):
        CenterConfiguration(directory=tmp_path).require_files()


def test_library_profile_does_not_require_host_contact_content(tmp_path):
    """A standalone clinical host needs policy files, not web contact information."""
    for name in ("clinical_vocabulary.toml", "filter_flag_metadata.yaml"):
        (tmp_path / name).write_text("")
    CenterConfiguration(directory=tmp_path).require_files()
    assert not (tmp_path / "contact.toml").exists()
