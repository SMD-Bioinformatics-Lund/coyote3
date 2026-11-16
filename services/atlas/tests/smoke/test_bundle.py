"""Fast offline checks of package identity and independent CLI imports."""

import os
import subprocess
import sys

from coyote_atlas import cli
from coyote_atlas.bundle import ReferenceBundle


def test_packaged_manifest_lists_both_reference_snapshots():
    manifest = ReferenceBundle.packaged().inspect()
    assert manifest.bundle_version == "1.0.0"
    assert {dataset.dataset_id for dataset in manifest.datasets} == {"hgnc_genes", "vep_metadata"}


def test_inspect_cli_needs_no_host_configuration(capsys):
    assert cli.main(["inspect"]) == 0
    assert '"bundle_id": "coyote-reference"' in capsys.readouterr().out


def test_offline_cli_modules_do_not_import_host_packages(tmp_path):
    environment = {
        key: value for key, value in os.environ.items() if key in {"PATH", "HOME", "LANG"}
    }
    environment["PYTHONPATH"] = str(ReferenceBundle.packaged().directory.parents[2])
    code = """
import importlib.abc, sys
class BlockHost(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname.split('.')[0] in {'coyote_api', 'coyote_mongo', 'fastapi', 'pymongo'}:
            raise AssertionError('Standalone import reached a host dependency')
sys.meta_path.insert(0, BlockHost())
from coyote_atlas.cli import main
assert main(['inspect']) == 0
"""
    result = subprocess.run(
        [sys.executable, "-c", code],
        env=environment,
        cwd=tmp_path,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
