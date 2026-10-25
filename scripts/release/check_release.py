#!/usr/bin/env python3
"""Validate application/SDK release identity and record a built library artifact."""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
import re
import subprocess
import tomllib
import zipfile
from email.parser import Parser
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
VERSION_PATTERN = re.compile(r"[0-9]+\.[0-9]+\.[0-9]+(?:(?:a|b|rc)[0-9]+|\.dev[0-9]+)?")


def validate_contract_generations(root: Path, release: dict[str, Any]) -> None:
    """Compare recorded generations with route declarations and the actual profile loader.

    Args:
        root: Checkout with HTTP routers and SDK configuration validation code.
        release: Application release declarations to verify.

    Raises:
        ValueError: A declared generation does not match the executable source contracts.
    """
    majors = set()
    for path in (root / "api/interfaces/http").rglob("*.py"):
        for node in ast.walk(ast.parse(path.read_text())):
            if not isinstance(node, ast.Call):
                continue
            router = isinstance(node.func, ast.Name) and node.func.id == "APIRouter"
            route = isinstance(node.func, ast.Attribute) and node.func.attr in {
                "get",
                "post",
                "put",
                "patch",
                "delete",
                "options",
                "head",
                "api_route",
            }
            if not router and not route:
                continue
            values = [
                keyword.value for keyword in node.keywords if keyword.arg in {"path", "prefix"}
            ]
            if route and node.args:
                values.append(node.args[0])
            for value in values:
                if isinstance(value, ast.Constant) and isinstance(value.value, str):
                    match = re.match(r"/api/v([0-9]+)(?:/|$)", value.value)
                    if match:
                        majors.add(int(match[1]))
    if not majors or max(majors) != release["http_api_major"]:
        raise ValueError("http_api_major differs from the declared HTTP route generations")
    selection = root / "src/coyote3/config/selection.py"
    actual_format = None
    for node in ast.parse(selection.read_text()).body:
        if isinstance(node, ast.Assign) and any(
            isinstance(target, ast.Name) and target.id == "CENTER_CONFIGURATION_FORMAT"
            for target in node.targets
        ):
            actual_format = ast.literal_eval(node.value)
    if actual_format != release["center_configuration_format"]:
        raise ValueError("center_configuration_format differs from the profile loader")


def release_identity(root: Path, *, sdk_only: bool = False) -> dict[str, Any]:
    """Validate the release pin and independently owned software versions.

    Args:
        root: Repository containing release.toml and SDK project metadata.
        sdk_only: Validate an SDK release without requiring application adoption.

    Returns:
        Release fields together with the SDK source version.

    Raises:
        ValueError: Versions, format identifiers, application pin or UI metadata disagree.
        OSError: A required release input is missing.
    """
    release = tomllib.loads((root / "release.toml").read_text())
    project = tomllib.loads((root / "pyproject.toml").read_text())["project"]
    for value in (release["application_version"], release["sdk_version"], project["version"]):
        if not isinstance(value, str) or not VERSION_PATTERN.fullmatch(value):
            raise ValueError(f"Unsupported release version: {value!r}")
    for field in ("http_api_major", "center_configuration_format"):
        if type(release[field]) is not int or release[field] < 1:
            raise ValueError(f"{field} must be a positive integer")
    if not sdk_only:
        validate_contract_generations(root, release)
        if release["sdk_version"] != project["version"]:
            raise ValueError("Application SDK pin differs from this checkout's SDK version")
        for path in ("package.json", "frontend/package.json"):
            if json.loads((root / path).read_text())["version"] != release["application_version"]:
                raise ValueError(
                    f"{path} differs from application_version; run npm run sync:version"
                )
    return {**release, "sdk_source_version": project["version"]}


def wheel_record(wheel: Path, expected_version: str) -> dict[str, str]:
    """Check a Coyote3 wheel's identity and retain its immutable digest.

    Args:
        wheel: Built wheel selected for the application deployment.
        expected_version: Exact SDK version required by the release record.

    Returns:
        Artifact filename, package version and SHA-256 digest.

    Raises:
        ValueError: Metadata is ambiguous, the identity differs, or the artifact
            contains retired core modules or the independent HTTP client.
        OSError: The artifact cannot be read.
        zipfile.BadZipFile: The artifact is not a valid wheel archive.
    """
    with zipfile.ZipFile(wheel) as archive:
        names = archive.namelist()
        metadata = [name for name in names if name.endswith(".dist-info/METADATA")]
        if len(metadata) != 1:
            raise ValueError("Expected exactly one wheel metadata record")
        message = Parser().parsestr(archive.read(metadata[0]).decode())
        if (
            str(message.get("Name", "")).lower() != "coyote3"
            or message["Version"] != expected_version
        ):
            raise ValueError("Wheel does not match the selected Coyote3 SDK version")
        retired = (
            "coyote3/client/",
            "coyote3_client/",
            "coyote3/config/bootstrap/",
            "coyote3/config/assets/",
            "coyote3/config/application_metadata.py",
            "coyote3/config/loaders/contact.py",
            "coyote3/config/clinical_query_seed.toml",
            "coyote3/application/provisioning/",
            "coyote3/application/resources/release_compilation.py",
            "coyote3/domain/core/",
            "coyote3/contracts/demo_installation.py",
            "coyote3/contracts/deployment_data.py",
            "coyote3/contracts/http.py",
            "coyote3/contracts/system.py",
            "coyote3/contracts/internal.py",
            "coyote3/contracts/client_errors.py",
            "coyote3/application/sdk/",
            "coyote3/config/center/",
            "coyote3/config/runtime.py",
            "coyote3/config/runtime_settings.py",
            "coyote3/config/security.py",
            "coyote3/config/mongo.py",
            "coyote3/config/app_config.py",
            "coyote3/config/collections.toml",
            "coyote3/application/common/file_access.py",
        )
        if any(name.startswith(retired) for name in names):
            raise ValueError("SDK wheel contains retired modules; rebuild from isolated source")
    return {
        "filename": wheel.name,
        "version": expected_version,
        "sha256": hashlib.sha256(wheel.read_bytes()).hexdigest(),
    }


def source_provenance(root: Path, *, production: bool) -> dict[str, Any]:
    """Capture source identity and reject unreleased work in production mode.

    Args:
        root: Git checkout being packaged.
        production: Require a clean reviewed source tree.

    Returns:
        Commit identifier and dirty-checkout status.

    Raises:
        ValueError: Production mode encounters modified or untracked source files.
        subprocess.CalledProcessError: Git cannot determine provenance.
    """
    commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, text=True).strip()
    dirty = bool(
        subprocess.check_output(["git", "status", "--porcelain"], cwd=root, text=True).strip()
    )
    if production and dirty:
        raise ValueError("Production release requires a clean source checkout")
    return {"source_commit": commit, "source_dirty": dirty}


def main() -> None:
    """Check release metadata and optionally write an application artifact record.

    Raises:
        ValueError: Release inputs or the wheel identity are inconsistent.
        subprocess.CalledProcessError: Git provenance cannot be determined.
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sdk-only", action="store_true")
    parser.add_argument("--wheel", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument(
        "--production", action="store_true", help="Reject dirty production releases"
    )
    args = parser.parse_args()
    if args.output and (not args.wheel or args.sdk_only):
        parser.error("--output requires --wheel and an application release check")
    if args.production and (not args.wheel or not args.output):
        parser.error("--production requires --wheel and --output")
    record = release_identity(ROOT, sdk_only=args.sdk_only)
    if args.wheel:
        expected = record["sdk_source_version"] if args.sdk_only else record["sdk_version"]
        record["sdk_artifact"] = wheel_record(args.wheel, expected)
    if args.output:
        record.update(source_provenance(ROOT, production=args.production))
        record["release_mode"] = "production" if args.production else "development"
        args.output.write_text(json.dumps(record, indent=2) + "\n")
    print("Release identity and selected artifacts are consistent.")


if __name__ == "__main__":
    main()
