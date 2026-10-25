#!/usr/bin/env python3
"""Verify the retained SDK wheel before installing it into an application image."""

import argparse
import hashlib
import json
import re
import sys
import tomllib
import zipfile
from email.parser import Parser
from pathlib import Path
from typing import Any


def verify_sdk_artifact(
    directory: Path, release_path: Path, *, production: bool, source_commit: str = "unknown"
) -> dict[str, Any]:
    """Require the image's SDK artifact to match its tested release record.

    Args:
        directory: Retained wheel and release-record.json directory.
        release_path: Application release selection copied into the image.
        production: Require a clean production record and matching source commit.
        source_commit: Image source commit; mandatory for production builds.

    Returns:
        Verified release record for retention with image provenance.

    Raises:
        ValueError: Identity, checksum, source provenance or release mode is inconsistent.
        OSError: Required artifact inputs cannot be read.
    """
    record = json.loads((directory / "release-record.json").read_text())
    release = tomllib.loads(release_path.read_text())
    for key in (
        "application_version",
        "sdk_version",
        "http_api_major",
        "center_configuration_format",
    ):
        if record.get(key) != release[key]:
            raise ValueError(f"SDK artifact record differs from application release: {key}")
    artifact = record.get("sdk_artifact") or {}
    filename = artifact.get("filename", "")
    if not filename or Path(filename).name != filename or not filename.endswith(".whl"):
        raise ValueError("SDK artifact must identify one wheel filename")
    wheel = directory / filename
    if sorted(path.name for path in directory.glob("*.whl")) != [filename]:
        raise ValueError("Artifact directory must contain exactly the selected wheel")
    if artifact.get("version") != release["sdk_version"]:
        raise ValueError("SDK artifact version differs from the application selection")
    if hashlib.sha256(wheel.read_bytes()).hexdigest() != artifact.get("sha256"):
        raise ValueError("SDK wheel checksum differs from the tested artifact")
    with zipfile.ZipFile(wheel) as archive:
        metadata = [name for name in archive.namelist() if name.endswith(".dist-info/METADATA")]
        if len(metadata) != 1:
            raise ValueError("SDK wheel has ambiguous metadata")
        message = Parser().parsestr(archive.read(metadata[0]).decode())
        if (
            str(message.get("Name", "")).lower() != "coyote3"
            or message["Version"] != release["sdk_version"]
        ):
            raise ValueError("SDK wheel metadata differs from the application selection")
    if production:
        if record.get("release_mode") != "production" or record.get("source_dirty") is not False:
            raise ValueError("Production image requires a clean production release record")
        if not re.fullmatch(r"[0-9a-f]{40}", source_commit):
            raise ValueError("Production image requires its exact GIT_COMMIT")
        if record.get("source_commit") != source_commit:
            raise ValueError("Image source commit differs from the tested SDK record")
    return record


def verify_compose_artifacts(config_path: Path, release_path: Path) -> None:
    """Check resolved local SDK build contexts before installation stages run.

    Args:
        config_path: JSON produced by Docker Compose's config command.
        release_path: Application release selection for this checkout.

    Raises:
        ValueError: A local SDK context, build mode or retained artifact is invalid.
        OSError: The rendered configuration or artifact inputs cannot be read.
    """
    config = json.loads(config_path.read_text())
    for name, service in config.get("services", {}).items():
        build = service.get("build")
        if not isinstance(build, dict):
            continue
        directory = build.get("additional_contexts", {}).get("sdk_artifact")
        if directory is None:
            continue
        arguments = build.get("args") or {}
        mode = arguments.get("COYOTE3_ARTIFACT_MODE", "production")
        if mode not in {"production", "development"}:
            raise ValueError(f"Invalid SDK artifact mode for service {name}")
        artifact_path = Path(directory)
        if not artifact_path.is_absolute():
            raise ValueError(
                f"SDK artifact context for service {name} must be a local absolute path"
            )
        try:
            verify_sdk_artifact(
                artifact_path,
                release_path,
                production=mode == "production",
                source_commit=arguments.get("GIT_COMMIT") or "unknown",
            )
        except (OSError, ValueError, zipfile.BadZipFile) as error:
            raise ValueError(
                f"SDK artifact preflight failed for {name} at {artifact_path}: {error}. "
                "Stage the tested release wheel and release-record.json in this directory, "
                "or set COYOTE3_SDK_ARTIFACT_DIR to their absolute directory. "
                "Use the matching source checkout and GIT_COMMIT. "
                "See docs/sdk/compatibility.md#build-and-record-an-application-release. "
                "The installer does not rebuild tested production artifacts."
            ) from error


def main() -> None:
    """Reject mismatched artifacts before pip installs any SDK code."""
    parser = argparse.ArgumentParser(description=__doc__)
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--directory", type=Path)
    source.add_argument("--compose-config", type=Path)
    parser.add_argument("--release", required=True, type=Path)
    parser.add_argument("--mode", choices=("production", "development"))
    parser.add_argument("--source-commit", default="unknown")
    args = parser.parse_args()
    if args.directory and not args.mode:
        parser.error("--directory requires --mode")
    try:
        if args.compose_config:
            verify_compose_artifacts(args.compose_config, args.release)
        else:
            verify_sdk_artifact(
                args.directory,
                args.release,
                production=args.mode == "production",
                source_commit=args.source_commit,
            )
    except (OSError, ValueError, zipfile.BadZipFile) as error:
        print(str(error), file=sys.stderr)
        raise SystemExit(1) from None
    if args.compose_config:
        print("SDK build input preflight passed.")
    else:
        print("SDK wheel matches its retained release record.")


if __name__ == "__main__":
    main()
