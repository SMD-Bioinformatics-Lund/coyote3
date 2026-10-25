"""Select a supported host Python independently of sudo's system PATH."""

import os
import shlex
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
HELPER = ROOT / "scripts/deployment/python_runtime.sh"


@pytest.mark.parametrize("explicit", [False, True])
def test_deployment_selects_supported_python_over_old_system_default(tmp_path, explicit):
    """A sanitized PATH must not hide the repository or explicitly selected Python."""
    binaries = tmp_path / "bin"
    binaries.mkdir()
    obsolete = binaries / "python3"
    obsolete.write_text("#!/bin/bash\nexit 1\n")
    obsolete.chmod(0o700)
    interpreter = tmp_path / ("custom python" if explicit else ".venv/bin/python")
    interpreter.parent.mkdir(parents=True, exist_ok=True)
    interpreter.symlink_to(sys.executable)
    environment = {**os.environ, "PATH": f"{binaries}:/usr/bin:/bin"}
    environment.pop("PYTHON_BIN", None)
    if explicit:
        environment["PYTHON_BIN"] = str(interpreter)
    result = subprocess.run(
        [
            "/bin/bash",
            "-c",
            'source "$1"; select_deployment_python "$2" && '
            '"$PYTHON_BIN" -c "import tomllib" && printf "%s" "$PYTHON_BIN"',
            "python-selection",
            str(HELPER),
            str(tmp_path),
        ],
        env=environment,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout == str(interpreter)


def test_invalid_explicit_python_stops_before_deployment(tmp_path):
    """An explicit unsupported interpreter produces an actionable prerequisite error."""
    obsolete = tmp_path / "old-python"
    obsolete.write_text("#!/bin/bash\nexit 1\n")
    obsolete.chmod(0o700)
    result = subprocess.run(
        ["/bin/bash", "-c", f"source {shlex.quote(str(HELPER))}; select_deployment_python ."],
        env={**os.environ, "PYTHON_BIN": str(obsolete)},
        capture_output=True,
        text=True,
    )
    assert result.returncode == 1
    assert "Python 3.12 or later" in result.stderr
    assert "not a package to install" in result.stderr
