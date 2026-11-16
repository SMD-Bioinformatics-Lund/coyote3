"""Normal wheels work outside the checkout with independent library and service imports."""

import json
import os
import subprocess
import sys
import zipfile
from email.parser import Parser
from pathlib import Path

import pytest

from scripts.release.build_sdk import build_sdk
from scripts.release.check_release import release_identity, wheel_record
from scripts.release.verify_sdk_artifact import verify_sdk_artifact

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture(scope="module")
def installed_distributions(tmp_path_factory):
    """Build actual wheels and install them into separate targets with no dependency downloads."""
    root = tmp_path_factory.mktemp("installed-distributions")
    wheels = root / "wheels"
    build_sdk(wheels, build_isolation=False)
    core = next(wheels.glob("coyote_core-*.whl"))
    server = next(wheels.glob("coyote_server-*.whl"))
    client = next(wheels.glob("coyote_pyclient-*.whl"))
    relay = next(wheels.glob("coyote_relay-*.whl"))
    atlas = next(wheels.glob("coyote_atlas-*.whl"))
    demo = next(wheels.glob("coyote_demo-*.whl"))
    for name, selected in (
        ("core", [core]),
        ("adapter", [core, server]),
        ("server", [core, server]),
        ("client", [client]),
        ("relay", [core, client, relay]),
        ("worker", [core, server, client, relay]),
        ("atlas", [core, client, atlas]),
        ("demo", [core, demo]),
        ("extensions", [core, server, client, relay, atlas, demo]),
    ):
        subprocess.run(
            [
                sys.executable,
                "-m",
                "pip",
                "install",
                "--no-deps",
                "--target",
                str(root / name),
                *(str(wheel) for wheel in selected),
            ],
            check=True,
            capture_output=True,
        )
    return (
        root,
        {
            "coyote-core": core,
            "coyote-server": server,
            "coyote-relay": relay,
            "coyote-atlas": atlas,
            "coyote-demo": demo,
        },
        client,
    )


def run_installed(root, target, code):
    """Run an installed package from an unrelated directory with editable finders removed."""
    bootstrap = (
        "import sys; from pathlib import Path; "
        f"target=Path({str(root / target)!r}); sys.path.insert(0,str(target)); "
        "sys.meta_path[:]=[f for f in sys.meta_path if not getattr(f,'__module__',type(f).__module__).startswith('__editable__')];\n"
        # Keep third-party dependencies, but isolate installed first-party plugin metadata too.
        "import importlib.metadata as metadata\n"
        "ambient_distributions = metadata.distributions\n"
        "def installed_distributions(**kwargs):\n"
        "    for package in ambient_distributions(**kwargs):\n"
        "        if package.metadata['Name'] in {'coyote-core','coyote-server','coyote-pyclient','coyote-relay','coyote-atlas','coyote-demo'} and Path(package.locate_file('')).resolve() != target.resolve():\n"
        "            continue\n"
        "        yield package\n"
        "metadata.distributions = installed_distributions\n"
    )
    env = {
        **os.environ,
        "ENV_NAME": "test",
        "TESTING": "1",
        "DEVELOPMENT": "0",
        "SECRET_KEY": "synthetic-installation-test-secret",
        "INTERNAL_API_TOKEN": "synthetic-installation-test-token",
        "COYOTE_DEMO_ENABLED": "0",
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


def test_actual_deployment_wheels_pass_retained_record_verification(installed_distributions):
    """Every deployment wheel must match the retained artifact record."""
    root, packages, client = installed_distributions
    record = release_identity(ROOT)
    selections = {
        "coyote-core": record["sdk_version"],
        "coyote-server": record["server_version"],
        "coyote-pyclient": record["client_version"],
        "coyote-relay": record["relay_version"],
        "coyote-atlas": record["atlas_version"],
        "coyote-demo": record["demo_version"],
    }
    record.update(
        source_commit="a" * 40,
        source_dirty=True,
        release_mode="development",
        artifacts={
            distribution: wheel_record(wheel, selections[distribution], distribution)
            for distribution, wheel in {**packages, "coyote-pyclient": client}.items()
        },
    )
    directory = root / "wheels"
    (directory / "release-record.json").write_text(json.dumps(record))
    assert verify_sdk_artifact(directory, ROOT / "release.toml", production=False) == record


def test_core_wheel_imports_and_renders_without_server_or_client(installed_distributions):
    root, _, _ = installed_distributions
    run_installed(
        root,
        "core",
        """
import importlib.abc
class BlockHost(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname.split('.')[0] in {'coyote_api','coyote_mongo','fastapi','starlette','pymongo','bson','coyote_pyclient','coyote_relay'}:
            raise AssertionError('Core imported host dependency: '+fullname)
sys.meta_path.insert(0,BlockHost())
import coyote
assert Path(coyote.__file__).is_relative_to(target)
from importlib.metadata import version
assert coyote.__version__ == version('coyote-core')
from coyote.application.operations import CoyoteApplication
from coyote.config.governance_catalog import RBAC_CATALOG_DIR, load_governance_catalog
assert RBAC_CATALOG_DIR.is_relative_to(target)
assert 'sample:view' in {item['permission_id'] for item in load_governance_catalog('permissions')}
assert 'superuser' in {item['role_id'] for item in load_governance_catalog('roles')}
from coyote.config.vep_reference import VEP_METADATA_POLICY_PATH, load_vep_metadata_policy
assert VEP_METADATA_POLICY_PATH.is_relative_to(target)
assert load_vep_metadata_policy()['consequence_groups']
from coyote.application.reporting.report_renderer import render_report_html, render_pdf_bytes
for analyte,name in [('dna','smd/dna_report.html'),('rna','smd/report_fusion.html')]:
    html=render_report_html(template_name=name,template_context={'sample':{'name':'SYNTHETIC'},'assay_config':{'reporting':{}},'report_sections':[],'report_sections_data':{},'fusions':[],'genes_covered_in_panel':{}},snapshot_rows=[],analyte=analyte,preview=True)
    assert 'SYNTHETIC' in html and '<style' in html
    assert 'name="smd-reports:package_version"' in html
    assert render_pdf_bytes(html).startswith(b'%PDF-')
""",
    )


def test_mongo_component_imports_without_api_or_http_frameworks(installed_distributions):
    """Importing the adapter does not load the API or its HTTP framework."""
    root, _, _ = installed_distributions
    run_installed(
        root,
        "adapter",
        """
import importlib.abc
class BlockHost(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname.split('.')[0] in {'coyote_api','fastapi','starlette','coyote_pyclient','coyote_relay'}:
            raise AssertionError('Adapter imported host: '+fullname)
sys.meta_path.insert(0,BlockHost())
import coyote_mongo
assert Path(coyote_mongo.__file__).is_relative_to(target)
from importlib.metadata import version
assert coyote_mongo.__version__ == version('coyote-server')
from coyote_mongo.runtime_adapter import MongoAdapter
from coyote_mongo.sessions import MongoApiSessionRepository
from coyote_mongo.config.collections import load_collection_mapping
assert load_collection_mapping()['primary']['samples_collection']=='samples'
adapter=MongoAdapter()
assert adapter.client is None
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
        if fullname.split('.')[0] in {'coyote_api','coyote_mongo','coyote','fastapi','starlette','pymongo','bson','coyote_relay'}:
            raise AssertionError('Client imported server: '+fullname)
sys.meta_path.insert(0,BlockCore())
import asyncio, coyote_pyclient
assert Path(coyote_pyclient.__file__).is_relative_to(target)
from coyote_pyclient import CoyoteClient, AsyncCoyoteClient
with CoyoteClient('https://example.test') as client:
    assert client.user is None
async def check():
    async with AsyncCoyoteClient('https://example.test') as client:
        assert client.user is None
asyncio.run(check())
""",
    )


def test_server_asgi_entry_and_assets_exist_outside_checkout(installed_distributions):
    root, packages, _ = installed_distributions
    with zipfile.ZipFile(packages["coyote-server"]) as wheel:
        members = set(wheel.namelist())
        source = ROOT / "api/src/coyote_api"
        assert not any("bootstrap/demo_data/" in name for name in members)
        assert not any("hgnc_genes.seed" in name or "vep_metadata.seed" in name for name in members)
        for directory in ("config/examples/center",):
            files = [path for path in (source / directory).rglob("*") if path.is_file()]
            assert files, directory
            for path in files:
                assert f"coyote_api/{path.relative_to(source).as_posix()}" in members
    run_installed(
        root,
        "server",
        """
import coyote_api
assert Path(coyote_api.__file__).is_relative_to(target)
from uvicorn.importer import import_from_string
app=import_from_string('coyote_api.app.main:app')
from coyote_api.version import APPLICATION_VERSION, __version__, environment_version
from importlib.metadata import version
assert app.version == __version__ == version('coyote-server')
assert environment_version('production') == APPLICATION_VERSION
assert '/api/v1/samples/{sample_id}/reports/{report_type}/preview/bundle' in app.openapi()['paths']
assert app.state.api_extensions == ()
assert not any('/internal/ingest/' in path for path in app.openapi()['paths'])
assert 'Sample ingestion' not in {tag['name'] for tag in app.openapi()['tags']}
from coyote_api.config.paths import CENTER_CONFIG_DIR
from coyote.config.governance_catalog import RBAC_CATALOG_DIR
assert CENTER_CONFIG_DIR.is_relative_to(target)
assert (CENTER_CONFIG_DIR/'contact.toml').is_file()
assert (RBAC_CATALOG_DIR/'permissions.seed.ndjson').is_file()
assert (target/'coyote_api/app/templates/api_reference.html').is_file()
from coyote_api.cli import main
sys.argv=['coyote4-api','--help']
try: main()
except SystemExit as exc: assert exc.code==0
""",
    )


def test_ingestion_submission_entrypoints_work_without_server(installed_distributions):
    """Submission, login and validation commands need only the core and HTTP client."""
    root, _, _ = installed_distributions
    run_installed(
        root,
        "relay",
        """
import importlib.abc
class BlockHost(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname.split('.')[0] in {'coyote_api','coyote_mongo','fastapi','starlette','pymongo','bson','celery'}:
            raise AssertionError('Ingestion submission imported server: '+fullname)
sys.meta_path.insert(0,BlockHost())
import coyote_relay
assert Path(coyote_relay.__file__).is_relative_to(target)
from importlib.metadata import distribution
package = distribution('coyote-relay')
assert package.version == '1.0.0'
assert {e.name for e in package.entry_points if e.group == 'console_scripts'} == {
    'coyote-relay-submit', 'coyote-relay-login', 'coyote-relay-validate', 'coyote-relay-worker'
}
assert [(e.name, e.value) for e in package.entry_points if e.group == 'coyote.api.routers'] == [
    ('relay', 'coyote_relay.api:routers')
]
assert (target/'coyote_relay/assets/coyote-relay-logo.svg').is_file()
for entry in package.entry_points:
    if entry.group == 'console_scripts' and entry.name != 'coyote-relay-worker':
        sys.argv = [entry.name, '--help']
        try: entry.load()()
        except SystemExit as exc: assert exc.code == 0, entry.name
""",
    )


def test_installed_ingestion_worker_registers_durable_tasks(installed_distributions):
    """The worker extra resolves its own task app without a source checkout or live broker."""
    root, _, _ = installed_distributions
    run_installed(
        root,
        "worker",
        """
from coyote_relay.celery_app import celery_app
celery_app.loader.import_default_modules()
assert 'coyote_relay.tasks.ingest_sample_bundle' in celery_app.tasks
assert 'coyote_relay.tasks.dispatch_pending_jobs' in celery_app.tasks
from importlib.metadata import distribution
entry = next(e for e in distribution('coyote-relay').entry_points if e.name == 'coyote-relay-worker')
assert callable(entry.load())
from coyote_api.app.main import app
assert app.state.api_extensions == ('relay',)
paths = app.openapi()['paths']
assert '/api/v1/internal/ingest/sample-bundle/upload' in paths
assert '/api/v1/internal/ingest/collection' in paths
assert '/api/v1/internal/tasks/{task_id}' in paths
assert {'IngestToken': []} in paths['/api/v1/internal/ingest/sample-bundle/upload']['post']['security']
""",
    )


@pytest.mark.parametrize("service", ["atlas", "demo"])
def test_reference_and_demo_tools_run_without_server(installed_distributions, service):
    """Offline data validation needs no API, database driver or checkout."""
    root, _, _ = installed_distributions
    run_installed(
        root,
        service,
        f"""
import importlib.abc
class BlockHost(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname.split('.')[0] in {{'coyote_api','coyote_mongo','fastapi','pymongo','bson'}}:
            raise AssertionError('Offline tool imported server: '+fullname)
sys.meta_path.insert(0, BlockHost())
from importlib.metadata import distribution
package = distribution('coyote-{service}')
assert (target/'coyote_{service}/assets/coyote-{service}-logo.svg').is_file()
for entry in package.entry_points:
    if entry.group == 'console_scripts':
        sys.argv = [entry.name, '--help']
        try: entry.load()()
        except SystemExit as exc: assert exc.code == 0
""",
    )


def test_installed_optional_extensions_keep_demo_disabled(installed_distributions):
    """Installing Demo alone never exposes reset/install routes on the normal host."""
    root, _, _ = installed_distributions
    run_installed(
        root,
        "extensions",
        """
from coyote_api.app.main import app
assert app.state.api_extensions == ('atlas', 'relay')
assert '/api/v1/admin/references/plan' in app.openapi()['paths']
assert not any('/demo/' in route.path for route in app.routes if hasattr(route, 'path'))
from coyote_api.bootstrap.references import reference_bundle
assert reference_bundle().plan().collections['hgnc_genes'] > 40000
""",
    )


def test_wheel_metadata_declares_only_its_own_package_and_license(
    installed_distributions,
):
    _, packages, client = installed_distributions
    expected = {
        "coyote-core": ("coyote/",),
        "coyote-server": ("coyote_api/", "coyote_mongo/"),
        "coyote-relay": ("coyote_relay/",),
        "coyote-atlas": ("coyote_atlas/",),
        "coyote-demo": ("coyote_demo/",),
    }
    for package, artifact in packages.items():
        with zipfile.ZipFile(artifact) as wheel:
            names = wheel.namelist()
            metadata = Parser().parsestr(
                wheel.read(next(n for n in names if n.endswith("/METADATA"))).decode()
            )
            assert metadata["Name"] == package
            assert metadata["Author"] == "Ram Nanduri"
            assert metadata["License-Expression"] == "GPL-3.0-only"
            assert {"LICENSE.txt", "COPYRIGHT.txt", "NOTICE.txt"} <= {
                Path(name).name for name in names if ".dist-info/licenses/" in name
            }
            for prefix in expected[package]:
                assert any(name.startswith(prefix) for name in names)
            assert not any(
                name.startswith(
                    tuple(
                        prefix
                        for key, prefixes in expected.items()
                        if key != package
                        for prefix in prefixes
                    )
                )
                for name in names
            )
            assert not any(
                name.startswith(("coyote4/", "coyote_pyclient/", "coyote/templates/reporting/"))
                for name in names
            )
            if package == "coyote-core":
                assert not any(
                    r.lower().startswith(("fastapi", "pymongo", "coyote-server"))
                    for r in metadata.get_all("Requires-Dist")
                )
            elif package == "coyote-server":
                assert not any(
                    r.lower().startswith(("coyote-relay", "coyote-atlas", "coyote-demo"))
                    for r in metadata.get_all("Requires-Dist")
                )
            elif package == "coyote-relay":
                requirements = metadata.get_all("Requires-Dist")
                assert "coyote-core==4.0.0" in requirements
                assert "coyote-pyclient==1.0.0" in requirements
                assert 'coyote-server==1.0.0; extra == "worker"' in requirements
                assert 'coyote-server==1.0.0; extra == "api"' in requirements
    with zipfile.ZipFile(client) as wheel:
        names = wheel.namelist()
        assert not any(
            n.startswith(("coyote/", "coyote4/", "coyote_api/", "coyote_mongo/")) for n in names
        )
        metadata = Parser().parsestr(
            wheel.read(next(n for n in names if n.endswith("/METADATA"))).decode()
        )
        assert metadata["License-Expression"] == "GPL-3.0-only"
        assert {"LICENSE.txt", "COPYRIGHT.txt", "NOTICE.txt"} <= {
            Path(name).name for name in names if ".dist-info/licenses/" in name
        }
        assert not any(
            r.lower().startswith(("coyote-core", "coyote-server", "fastapi", "pymongo"))
            for r in metadata.get_all("Requires-Dist")
        )
