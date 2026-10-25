"""Normal wheels work outside the checkout with independent core and client imports."""

import os
import subprocess
import sys
import zipfile
from email.parser import Parser
from pathlib import Path

import pytest

from scripts.release.build_sdk import build_sdk

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture(scope="module")
def installed_distributions(tmp_path_factory):
    """Build actual wheels and install them into separate targets with no dependency downloads."""
    root = tmp_path_factory.mktemp("installed-distributions")
    wheels = root / "wheels"
    build_sdk(wheels, build_isolation=False)
    subprocess.run(
        [
            sys.executable,
            "-m",
            "pip",
            "wheel",
            "--no-deps",
            "--no-build-isolation",
            "--wheel-dir",
            str(wheels),
            str(ROOT / "clients/python"),
        ],
        check=True,
        capture_output=True,
    )
    server = next(wheels.glob("coyote3-*.whl"))
    client = next(wheels.glob("coyote3_client-*.whl"))
    for name, wheel in (("server", server), ("client", client)):
        subprocess.run(
            [
                sys.executable,
                "-m",
                "pip",
                "install",
                "--no-deps",
                "--target",
                str(root / name),
                str(wheel),
            ],
            check=True,
            capture_output=True,
        )
    return root, server, client


def run_installed(root, target, code):
    """Run an installed package from an unrelated directory with editable finders removed."""
    bootstrap = (
        "import sys; from pathlib import Path; "
        f"target=Path({str(root / target)!r}); sys.path.insert(0,str(target)); "
        "sys.meta_path[:]=[f for f in sys.meta_path if not getattr(f,'__module__',type(f).__module__).startswith('__editable__')];\n"
    )
    env = {
        **os.environ,
        "ENV_NAME": "test",
        "TESTING": "1",
        "DEVELOPMENT": "0",
        "SECRET_KEY": "synthetic-installation-test-secret",
        "INTERNAL_API_TOKEN": "synthetic-installation-test-token",
    }
    result = subprocess.run(
        [sys.executable, "-I", "-c", bootstrap + code],
        cwd=root,
        env=env,
        check=False,
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert result.returncode == 0, result.stdout + result.stderr


def test_core_wheel_imports_and_renders_without_server_or_client(installed_distributions):
    root, _, _ = installed_distributions
    run_installed(
        root,
        "server",
        """
import importlib.abc
class BlockHost(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname.split('.')[0] in {'api','fastapi','starlette','pymongo','bson','coyote3_client'}:
            raise AssertionError('Core imported host dependency: '+fullname)
sys.meta_path.insert(0,BlockHost())
import coyote3
assert Path(coyote3.__file__).is_relative_to(target)
from coyote3.application.operations import CoyoteApplication
from coyote3.application.reporting.report_renderer import render_report_html, render_pdf_bytes
for analyte,name in [('dna','dna_report.html'),('rna','report_fusion.html')]:
    for layout in ['legacy','modern']:
        html=render_report_html(template_name=name,template_context={'sample':{'name':'SYNTHETIC'},'assay_config':{'reporting':{}},'report_sections':[],'report_sections_data':{},'fusions':[],'genes_covered_in_panel':{}},snapshot_rows=[],analyte=analyte,preview=True,layout=layout)
        assert 'SYNTHETIC' in html and '<style' in html
        assert render_pdf_bytes(html).startswith(b'%PDF-')
""",
    )


def test_client_wheel_imports_without_core_or_server(installed_distributions):
    root, _, _ = installed_distributions
    run_installed(
        root,
        "client",
        """
import importlib.abc
class BlockCore(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname.split('.')[0] in {'api','coyote3','fastapi','starlette','pymongo','bson'}:
            raise AssertionError('Client imported server: '+fullname)
sys.meta_path.insert(0,BlockCore())
import asyncio, coyote3_client
assert Path(coyote3_client.__file__).is_relative_to(target)
from coyote3_client import CoyoteClient, AsyncCoyoteClient
with CoyoteClient('https://example.test') as client:
    assert client.user is None
async def check():
    async with AsyncCoyoteClient('https://example.test') as client:
        assert client.user is None
asyncio.run(check())
""",
    )


def test_server_asgi_entry_and_assets_exist_outside_checkout(installed_distributions):
    root, _, _ = installed_distributions
    run_installed(
        root,
        "server",
        """
import api
assert Path(api.__file__).is_relative_to(target)
from uvicorn.importer import import_from_string
app=import_from_string('api.app.main:app')
assert '/api/v1/samples/{sample_id}/reports/{report_type}/try-new' in app.openapi()['paths']
from api.config.paths import CENTER_CONFIG_DIR,DEMO_WORKFLOW_BUNDLE_PATH
from api.bootstrap.paths import BOOTSTRAP_ROOT
assert CENTER_CONFIG_DIR.is_relative_to(target)
assert (CENTER_CONFIG_DIR/'contact.toml').is_file()
assert (BOOTSTRAP_ROOT/'rbac/permissions.seed.ndjson').is_file()
assert (DEMO_WORKFLOW_BUNDLE_PATH/'README.md').is_file()
assert (target/'api/app/templates/api_reference.html').is_file()
from api.cli import main
sys.argv=['coyote3-api','--help']
try: main()
except SystemExit as exc: assert exc.code==0
""",
    )


def test_wheel_metadata_declares_extras_and_excludes_the_other_distribution(
    installed_distributions,
):
    _, server, client = installed_distributions
    with zipfile.ZipFile(server) as wheel:
        names = wheel.namelist()
        metadata = Parser().parsestr(
            wheel.read(next(n for n in names if n.endswith("/METADATA"))).decode()
        )
        assert {"api", "all"} <= set(metadata.get_all("Provides-Extra"))
        assert metadata["Author"] == "Ram Nanduri"
        assert metadata["License-Expression"] == "LicenseRef-COYOTE3-Free-Use-Source-Available-1.0"
        assert {"LICENSE.txt", "NOTICE.txt", "LICENSING.md", "THIRD_PARTY_NOTICES.md"} <= {
            Path(name).name for name in names if ".dist-info/licenses/" in name
        }
        assert not any(n.startswith(("coyote3/client/", "coyote3_client/")) for n in names)
        assert "api/app/main.py" in names and "api/release.toml" in names
        assert "api/bootstrap/catalogs/reference/LICENSE.txt" in names
        assert "coyote3/templates/reporting/base.html" in names
        requirements = metadata.get_all("Requires-Dist")
        assert not any("fastapi" in r.lower() and ";" not in r for r in requirements)
    with zipfile.ZipFile(client) as wheel:
        names = wheel.namelist()
        assert not any(n.startswith(("coyote3/", "api/")) for n in names)
        metadata = Parser().parsestr(
            wheel.read(next(n for n in names if n.endswith("/METADATA"))).decode()
        )
        assert metadata["License-Expression"] == "Apache-2.0"
        assert {"LICENSE.txt", "NOTICE.txt"} <= {
            Path(name).name for name in names if ".dist-info/licenses/" in name
        }
        assert not any(
            r.lower().startswith(("coyote3", "fastapi", "pymongo"))
            for r in metadata.get_all("Requires-Dist")
        )
