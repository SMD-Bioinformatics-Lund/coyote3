"""Check host storage preparation without Docker or database access."""

import hashlib
import json
import os
import subprocess
import tomllib
from pathlib import Path

import pytest

from scripts.deployment.prepare_host_directories import (
    check_directory_access,
    prepare,
    prepare_accreditation_logo,
)


def test_preparation_imports_host_logo_into_read_only_center_mount(tmp_path):
    """Container creation imports the image, preserves contact text, and is repeatable."""
    source = tmp_path / "host artwork" / "logo.svg"
    source.parent.mkdir()
    content = b'<svg xmlns="http://www.w3.org/2000/svg" width="24mm" height="28mm"/>'
    source.write_bytes(content)
    center = tmp_path / "center"
    center.mkdir()
    contact = center / "contact.toml"
    contact.write_text(
        '# Center identity\n[organization]\nname = "Synthetic"\n'
        f'accreditation_logo = "{source}" # Accreditation\n\n[links]\nhelp = ""\n'
    )
    manifest_path = center / "manifest.json"
    manifest_path.write_text(json.dumps({"sha256": {}, "source": "synthetic"}))
    config = configuration(tmp_path)
    config["services"]["api"]["volumes"].append(
        {"type": "bind", "source": str(center), "target": "/app/center-config", "read_only": True}
    )
    prepare(config)
    updated = contact.read_text()
    relative = tomllib.loads(updated)["organization"]["accreditation_logo"]
    assert relative.startswith("logos/accreditation-")
    assert (center / relative).read_bytes() == content
    assert source.read_bytes() == content
    manifest = json.loads(manifest_path.read_text())
    assert manifest["source"] == "synthetic"
    assert manifest["sha256"][relative] == hashlib.sha256(content).hexdigest()
    assert manifest["sha256"]["contact.toml"] == hashlib.sha256(contact.read_bytes()).hexdigest()
    assert "# Center identity" in updated and "# Accreditation" in updated
    assert tomllib.loads(updated)["links"] == {"help": ""}
    prepare(config)
    assert contact.read_text() == updated
    assert len(list((center / "logos").iterdir())) == 1


@pytest.mark.parametrize("value", ["", "logos/local.svg"])
def test_relative_accreditation_setting_is_unchanged(tmp_path, value):
    """Existing container-relative configuration requires no host writes."""
    contact = tmp_path / "contact.toml"
    original = f'[organization]\naccreditation_logo = "{value}"\n'
    contact.write_text(original)
    prepare_accreditation_logo(tmp_path)
    assert contact.read_text() == original
    assert not (tmp_path / "logos").exists()


@pytest.mark.parametrize("failure", ["missing", "unsupported", "symlink"])
def test_invalid_accreditation_import_preserves_contact(tmp_path, failure):
    """Failed imports never replace the configured path or write through directory symlinks."""
    source = tmp_path / ("logo.txt" if failure == "unsupported" else "logo.svg")
    if failure != "missing":
        source.write_text('<svg xmlns="http://www.w3.org/2000/svg"/>')
    contact = tmp_path / "contact.toml"
    original = f'[organization]\naccreditation_logo = "{source}"\n'
    contact.write_text(original)
    if failure == "symlink":
        other = tmp_path / "outside"
        other.mkdir()
        (tmp_path / "logos").symlink_to(other, target_is_directory=True)
    with pytest.raises((OSError, ValueError)):
        prepare_accreditation_logo(tmp_path)
    assert contact.read_text() == original


def configuration(tmp_path):
    """Return a resolved synthetic Compose service with local temporary mounts."""
    return {
        "services": {
            "api": {
                "user": f"{os.getuid()}:{os.getgid()}",
                "environment": {"ENV_NAME": "production"},
                "volumes": [
                    {"type": "bind", "source": str(tmp_path / name), "target": target}
                    for name, target in (("data", "/data"), ("logs", "/app/logs"))
                ]
                + [
                    {
                        "type": "bind",
                        "source": str(tmp_path / "inputs"),
                        "target": "/inputs",
                        "read_only": True,
                    }
                ],
            }
        }
    }


def test_preparation_creates_runtime_tree_and_preserves_existing_files(tmp_path):
    """Reruns preserve data and modes; unrelated input folders remain absent."""
    config = configuration(tmp_path)
    prepare(config)
    runtime = tmp_path / "data/coyote3_prod"
    assert (runtime / "reports").is_dir()
    assert (runtime / "ingest_staging").is_dir()
    assert (runtime / "copied_sample_files/yaml").is_dir()
    assert (tmp_path / "logs").is_dir()
    assert not (tmp_path / "inputs").exists()
    report = runtime / "reports/existing.txt"
    report.write_text("preserved")
    (runtime / "reports").chmod(0o700)
    prepare(config)
    assert report.read_text() == "preserved"
    assert (runtime / "reports").stat().st_mode & 0o777 == 0o700


def test_preparation_rejects_file_instead_of_directory(tmp_path):
    """Storage preparation never overwrites a file at a configured root."""
    (tmp_path / "data").write_text("preserved")
    with pytest.raises(NotADirectoryError):
        prepare(configuration(tmp_path))
    assert (tmp_path / "data").read_text() == "preserved"


def test_preparation_rejects_inaccessible_existing_storage_without_chmod(tmp_path):
    """An incompatible container identity fails without changing existing permissions."""
    config = configuration(tmp_path)
    prepare(config)
    data = tmp_path / "data"
    data.chmod(0o700)
    config["services"]["api"]["user"] = "123456:123456"
    with pytest.raises(PermissionError, match="Existing permissions were not changed"):
        prepare(config)
    assert data.stat().st_mode & 0o777 == 0o700


def test_bind_mount_access_does_not_require_container_access_to_host_parents(tmp_path):
    """A private host parent is outside the bind mount and must remain private."""
    tmp_path.chmod(0o700)
    source = tmp_path / "mount"
    source.mkdir(mode=0o777)
    source.chmod(0o777)
    check_directory_access(source, 123456, 123456, mount_root=source)
    assert tmp_path.stat().st_mode & 0o777 == 0o700
    private = source / "private"
    private.mkdir(mode=0o700)
    nested = private / "nested"
    nested.mkdir(mode=0o777)
    nested.chmod(0o777)
    with pytest.raises(PermissionError, match="Existing permissions were not changed"):
        check_directory_access(nested, 123456, 123456, mount_root=source)


def test_wrapper_prepares_before_up_but_not_plain_config(tmp_path):
    """Deployment creates storage before Compose up; ordinary config stays read-only."""
    config = tmp_path / "render.json"
    config.write_text(json.dumps(configuration(tmp_path)))
    binary = tmp_path / "docker"
    binary.write_text(
        "#!/usr/bin/env python3\nimport sys,os,pathlib\n"
        "if sys.argv[-1] == 'version': sys.exit(0)\n"
        "if 'config' in sys.argv:\n"
        " print(pathlib.Path(os.environ['TEST_COMPOSE_JSON']).read_text())\n"
        "else:\n"
        " assert pathlib.Path(os.environ['TEST_STORAGE_ROOT'], 'data/coyote3_prod/reports').is_dir()\n"
    )
    binary.chmod(0o755)
    env = dict(
        os.environ,
        PATH=str(tmp_path) + os.pathsep + os.environ["PATH"],
        ENV_NAME="production",
        TEST_COMPOSE_JSON=str(config),
        TEST_STORAGE_ROOT=str(tmp_path),
    )
    root = Path(__file__).resolve().parents[2]
    command = ["bash", str(root / "scripts/deployment/compose-with-version.sh")]
    subprocess.run([*command, "config"], env=env, check=True, capture_output=True)
    assert not (tmp_path / "data").exists()
    subprocess.run([*command, "up", "-d"], env=env, check=True, capture_output=True)
    assert (tmp_path / "data/coyote3_prod/reports").is_dir()
