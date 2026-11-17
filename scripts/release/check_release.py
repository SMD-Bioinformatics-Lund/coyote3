#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Ram Nanduri
# SPDX-License-Identifier: GPL-3.0-only

"""Validate application release identity and record its tested deployment wheels."""

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

from .build_sdk import RelayArtifact

ROOT = Path(__file__).resolve().parents[2]
VERSION_PATTERN = re.compile(r"([0-9]+)\.([0-9]+)\.([0-9]+)(?:(a|b|rc|\.dev)([0-9]+))?")
# Version field -> changelogs and inputs that require a new wheel at release time.
RELEASE_CHANGE_SCOPES = {
    "application_version": (("CHANGELOG.md",), ()),
    "sdk_version": (
        ("core/CHANGELOG.md",),
        ("core/src", "core/pyproject.toml", "core/build_support.py", "core/MANIFEST.in"),
    ),
    "server_version": (
        ("api/CHANGELOG.md", "adapters/mongo/CHANGELOG.md"),
        ("api/src", "adapters/mongo/src", "pyproject.toml", "package_build.py", "MANIFEST.in"),
    ),
    "relay_version": ((), ()),  # External package owns its changelog.
    "atlas_version": (
        ("services/atlas/CHANGELOG.md",),
        ("services/atlas/src", "services/atlas/pyproject.toml"),
    ),
    "demo_version": (
        ("services/demo/CHANGELOG.md",),
        ("services/demo/src", "services/demo/pyproject.toml"),
    ),
}


def _version_key(value: str) -> tuple[int, int, int, int, int]:
    """Order the supported development, prerelease and final version spellings."""
    match = VERSION_PATTERN.fullmatch(value)
    if not match:
        raise ValueError(f"Unsupported release version: {value!r}")
    major, minor, patch, phase, number = match.groups()
    return (
        int(major),
        int(minor),
        int(patch),
        {".dev": 0, "a": 1, "b": 2, "rc": 3, None: 4}[phase],
        int(number or 0),
    )


def validate_pull_request(
    root: Path,
    release: dict[str, Any],
    *,
    base_ref: str,
    target_branch: str,
    skip_changelog: bool = False,
) -> None:
    """Check changelog updates and release progression against the PR's base commit.

    Args:
        root: Checkout containing the proposed changes and local base history.
        release: Validated current release identity.
        base_ref: Local Git commit or ref identifying the target branch baseline.
        target_branch: Integration branch ``dev`` or release branch ``master``.
        skip_changelog: Waive only the ordinary root changelog edit requirement.

    Raises:
        ValueError: Notes, version progression or a changed release component is invalid.
        subprocess.CalledProcessError: The base commit or its metadata is unavailable.
        OSError: A required changelog cannot be read.
    """
    if target_branch not in {"dev", "master"}:
        raise ValueError("PR target must be dev or master")
    base = subprocess.check_output(
        ["git", "rev-parse", "--verify", "--end-of-options", f"{base_ref}^{{commit}}"],
        cwd=root,
        text=True,
    ).strip()
    changed = set(
        subprocess.check_output(
            ["git", "diff", "--name-only", "--no-renames", "-z", base, "--"],
            cwd=root,
        )
        .decode()
        .split("\0")
    )
    has_release_manifest = subprocess.check_output(
        ["git", "ls-tree", "--name-only", base, "--", "release.toml"],
        cwd=root,
        text=True,
    ).strip()
    if has_release_manifest:
        previous = tomllib.loads(
            subprocess.check_output(
                ["git", "show", f"{base}:release.toml"],
                cwd=root,
                text=True,
            )
        )
    else:
        # The first packaged release is compared with the application's existing
        # package.json identity on master, before release.toml was introduced.
        previous = {
            "application_version": json.loads(
                subprocess.check_output(
                    ["git", "show", f"{base}:package.json"],
                    cwd=root,
                    text=True,
                )
            )["version"]
        }

    if "CHANGELOG.md" not in changed and not skip_changelog:
        raise ValueError("Update CHANGELOG.md or obtain the skip-changelog-update label")
    for field, (changelogs, sources) in RELEASE_CHANGE_SCOPES.items():
        current = release[field]
        old = previous.get(field)
        if old is not None and _version_key(current) < _version_key(old):
            raise ValueError(f"{field} cannot decrease from {old} to {current}")
        if (
            target_branch == "master"
            and old is not None
            and _version_key(current) == _version_key(old)
        ):
            source_changed = any(
                path == source or path.startswith(source + "/")
                for path in changed
                for source in sources
            )
            if field == "application_version" or source_changed:
                raise ValueError(f"Advance {field} before releasing changes into master")
        for path in changelogs:
            if not re.search(
                rf"^##\s+\[?v{re.escape(current)}(?:\]|\s|$)",
                (root / path).read_text(),
                re.MULTILINE,
            ):
                raise ValueError(f"{path} needs a heading for version {current}")
            if current != old and path not in changed:
                raise ValueError(f"Update {path} for the new {field} {current}")


def validate_contract_generations(root: Path, release: dict[str, Any]) -> None:
    """Compare recorded generations with route declarations and the actual profile loader.

    Args:
        root: Checkout with HTTP routers and SDK configuration validation code.
        release: Application release declarations to verify.

    Raises:
        ValueError: A declared generation does not match the executable source contracts.
    """
    majors = set()
    for path in (root / "api/src/coyote_api/interfaces/http").rglob("*.py"):
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
    selection = root / "core/src/coyote/config/selection.py"
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
    project = tomllib.loads((root / "core/pyproject.toml").read_text())["project"]
    for value in (
        release["application_version"],
        release["sdk_version"],
        release["server_version"],
        release["relay_version"],
        release["atlas_version"],
        release["demo_version"],
        project["version"],
    ):
        if not isinstance(value, str) or not VERSION_PATTERN.fullmatch(value):
            raise ValueError(f"Unsupported release version: {value!r}")
    for field in ("http_api_major", "center_configuration_format"):
        if type(release[field]) is not int or release[field] < 1:
            raise ValueError(f"{field} must be a positive integer")
    if not sdk_only:
        validate_contract_generations(root, release)
        if release["sdk_version"] != project["version"]:
            raise ValueError("Application SDK pin differs from this checkout's SDK version")
        relay = RelayArtifact(root)
        lock = tomllib.loads((root / "uv.lock").read_text())
        selected_relay = [
            package for package in lock["package"] if package["name"] == "coyote-relay"
        ]
        expected_source = f"{relay.source['git']}?rev={relay.source['rev']}#{relay.source['rev']}"
        if len(selected_relay) != 1 or selected_relay[0]["version"] != release["relay_version"]:
            raise ValueError("coyote-relay version differs from the application selection")
        if selected_relay[0]["source"] != {"git": expected_source}:
            raise ValueError("Relay lockfile source differs from the selected Git commit")
        for relative, distribution, selected in (
            (".", "coyote-server", release["server_version"]),
            ("services/atlas", "coyote-atlas", release["atlas_version"]),
            ("services/demo", "coyote-demo", release["demo_version"]),
        ):
            package = tomllib.loads((root / relative / "pyproject.toml").read_text())["project"]
            if package["name"] != distribution or package["version"] != selected:
                raise ValueError(f"{distribution} version differs from the application selection")
            if (
                distribution == "coyote-server"
                and f"coyote-core=={release['sdk_version']}" not in package["dependencies"]
            ):
                raise ValueError("Server core dependency differs from the application selection")
            if distribution in {"coyote-atlas", "coyote-demo"}:
                if f"coyote-core=={release['sdk_version']}" not in package["dependencies"]:
                    raise ValueError(f"{distribution} core dependency differs from selection")
                if package.get("optional-dependencies", {}).get("api") != [
                    f"coyote-server=={release['server_version']}"
                ]:
                    raise ValueError(f"{distribution} API dependency differs from selection")
                if distribution == "coyote-demo" and package.get("optional-dependencies", {}).get(
                    "worker"
                ) != [
                    f"coyote-server=={release['server_version']}",
                    f"coyote-relay=={release['relay_version']}",
                ]:
                    raise ValueError("Demo worker dependencies differ from selection")
        application_identity = tomllib.loads(
            (root / "api/src/coyote_api/config/application_release.toml").read_text()
        )
        if application_identity != {"application_version": release["application_version"]}:
            raise ValueError("API application identity differs; run npm run sync:version")
        for path in ("package.json", "frontend/package.json"):
            if json.loads((root / path).read_text())["version"] != release["application_version"]:
                raise ValueError(
                    f"{path} differs from application_version; run npm run sync:version"
                )
    return {**release, "sdk_source_version": project["version"]}


def wheel_record(
    wheel: Path, expected_version: str, distribution: str = "coyote-core"
) -> dict[str, str]:
    """Check one independent wheel's identity, contents and immutable digest.

    Args:
        wheel: Built wheel selected for the application deployment.
        expected_version: Exact distribution version required by the release record.
        distribution: Required distribution name; defaults to the independent core.

    Returns:
        Artifact filename, package version and SHA-256 digest.

    Raises:
        ValueError: Metadata is ambiguous, the identity differs, or the artifact
            has missing namespaces, retired modules or another distribution's sources.
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
            str(message.get("Name", "")).lower().replace("_", "-") != distribution
            or message["Version"] != expected_version
        ):
            raise ValueError(f"Wheel does not match the selected {distribution} version")
        retired = (
            "api/",
            "coyote/client/",
            "coyote4/",
            "coyote/config/bootstrap/",
            "coyote/config/assets/",
            "coyote/config/application_metadata.py",
            "coyote/config/loaders/contact.py",
            "coyote/config/clinical_query_seed.toml",
            "coyote/application/provisioning/",
            "coyote/application/resources/release_compilation.py",
            "coyote/domain/core/",
            "coyote/contracts/demo_installation.py",
            "coyote/contracts/deployment_data.py",
            "coyote/contracts/http.py",
            "coyote/contracts/system.py",
            "coyote/contracts/internal.py",
            "coyote/contracts/client_errors.py",
            "coyote/application/sdk/",
            "coyote/config/center/",
            "coyote/config/runtime.py",
            "coyote/config/runtime_settings.py",
            "coyote/config/security.py",
            "coyote/config/mongo.py",
            "coyote/config/app_config.py",
            "coyote/config/collections.toml",
            "coyote/application/common/file_access.py",
        )
        if any(name.startswith(retired) for name in names):
            raise ValueError("SDK wheel contains retired modules; rebuild from isolated source")
        namespaces = {
            "coyote-core": ("coyote/",),
            "coyote-server": ("coyote_api/", "coyote_mongo/"),
            "coyote-relay": ("coyote_relay/",),
            "coyote-atlas": ("coyote_atlas/",),
            "coyote-demo": ("coyote_demo/",),
        }
        forbidden = tuple(
            prefix
            for package, prefixes in namespaces.items()
            if package != distribution
            for prefix in prefixes
        )
        if any(name.startswith(forbidden) for name in names):
            raise ValueError(f"{distribution} wheel contains another package's sources")
        for namespace in namespaces[distribution]:
            if not any(name.startswith(namespace) for name in names):
                raise ValueError(f"{distribution} wheel is missing its {namespace} namespace")
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
    parser.add_argument("--base-ref", help="Local PR base commit for version and changelog checks")
    parser.add_argument("--target-branch", choices=("dev", "master"))
    parser.add_argument(
        "--skip-changelog",
        action="store_true",
        help="Waive the ordinary root changelog edit; version changes still require release notes",
    )
    parser.add_argument("--sdk-only", action="store_true")
    parser.add_argument("--wheel-dir", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument(
        "--production", action="store_true", help="Reject dirty production releases"
    )
    args = parser.parse_args()
    if bool(args.base_ref) != bool(args.target_branch):
        parser.error("--base-ref and --target-branch must be supplied together")
    if args.skip_changelog and not args.base_ref:
        parser.error("--skip-changelog requires --base-ref")
    if args.base_ref and args.sdk_only:
        parser.error("PR checks require the complete application release identity")
    if args.output and (not args.wheel_dir or args.sdk_only):
        parser.error("--output requires --wheel-dir and an application release check")
    if args.production and (not args.wheel_dir or not args.output):
        parser.error("--production requires --wheel-dir and --output")
    record = release_identity(ROOT, sdk_only=args.sdk_only)
    if args.base_ref:
        validate_pull_request(
            ROOT,
            record,
            base_ref=args.base_ref,
            target_branch=args.target_branch,
            skip_changelog=args.skip_changelog,
        )
    if args.wheel_dir:
        selected = {
            "coyote-core": record["sdk_source_version"] if args.sdk_only else record["sdk_version"]
        }
        if not args.sdk_only:
            selected.update(
                {
                    "coyote-server": record["server_version"],
                    "coyote-relay": record["relay_version"],
                    "coyote-atlas": record["atlas_version"],
                    "coyote-demo": record["demo_version"],
                }
            )
        artifacts = {}
        for distribution, expected in selected.items():
            wheels = list(args.wheel_dir.glob(f"{distribution.replace('-', '_')}-{expected}-*.whl"))
            if len(wheels) != 1:
                raise ValueError(f"Expected one {distribution} wheel for version {expected}")
            artifacts[distribution] = wheel_record(wheels[0], expected, distribution)
        if {path.name for path in args.wheel_dir.glob("*.whl")} != {
            item["filename"] for item in artifacts.values()
        }:
            raise ValueError("Wheel directory contains unselected artifacts")
        record["artifacts"] = artifacts
    if args.output:
        record.update(source_provenance(ROOT, production=args.production))
        record["release_mode"] = "production" if args.production else "development"
        args.output.write_text(json.dumps(record, indent=2) + "\n")
    print("Release identity and selected artifacts are consistent.")
    if args.base_ref:
        print(f"Version and changelog checks passed for the PR into {args.target_branch}.")


if __name__ == "__main__":
    main()
