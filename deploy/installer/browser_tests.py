# SPDX-FileCopyrightText: 2026 Ram Nanduri
# SPDX-License-Identifier: GPL-3.0-only

"""Run browser acceptance against a new, disposable local demonstration stack."""

from __future__ import annotations

import argparse
import json
import os
import secrets
import socket
import subprocess
import sys
import time
import zipfile
from pathlib import Path
from typing import Any

import yaml
from coyote_demo.deployment import DEMO_DATABASES, validate_demo_target

from .demo import ROOT, load_settings, prepare
from .process import Console, Runner, redact

DOCKER = ["docker", "--host", "unix:///var/run/docker.sock"]


def validate_stack(configuration: dict[str, Any], project: str, port: int) -> None:
    """Reject shared storage, published databases and non-demo application targets.

    Args:
        configuration: Fully resolved Compose document; no ambient interpolation remains.
        project: Newly generated project identity belonging to this invocation.
        port: Newly selected loopback browser port.

    Raises:
        ValueError: A service could reach an ordinary deployment or shared storage.
    """
    if configuration.get("name") != project or not project.startswith("coyote4-demo-"):
        raise ValueError("Browser tests require their own generated demo project")
    networks = configuration.get("networks", {})
    if set(networks) != {"demo", "browser"} or networks["demo"].get("internal") is not True:
        raise ValueError("Browser tests require one isolated internal network")
    for resource in [*networks.values(), *configuration.get("volumes", {}).values()]:
        if resource.get("external") or not resource.get("name", "").startswith(project + "_"):
            raise ValueError("Browser tests cannot use existing networks or volumes")
    services = configuration.get("services", {})
    if set(services) != {
        "demo-mongo",
        "demo-replica",
        "demo-redis",
        "demo-storage",
        "demo-bootstrap",
        "api",
        "worker",
        "maintenance-worker",
        "beat",
        "frontend",
    }:
        raise ValueError("Unexpected browser test service topology")
    for name, service in services.items():
        if set(service.get("networks", {})) != (
            {"demo", "browser"} if name == "frontend" else {"demo"}
        ) or any(
            service.get(key) for key in ("network_mode", "privileged", "devices", "external_links")
        ):
            raise ValueError("Browser services cannot join external or host networks")
        if any(
            volume.get("type") != "volume" or volume.get("source") not in configuration["volumes"]
            for volume in service.get("volumes", [])
        ):
            raise ValueError("Browser services cannot mount host files or existing data")
        ports = service.get("ports", [])
        if name == "frontend":
            if len(ports) != 1 or any(
                (
                    ports[0].get("host_ip") != "127.0.0.1",
                    str(ports[0].get("published")) != str(port),
                    ports[0].get("target") != 3000,
                )
            ):
                raise ValueError("Only the generated loopback browser port may be published")
        elif ports:
            raise ValueError("Browser test databases and services cannot publish host ports")
        environment = service.get("environment", {})
        if name in {
            "api",
            "worker",
            "maintenance-worker",
            "beat",
            "demo-bootstrap",
            "demo-storage",
        }:
            validate_demo_target(environment)
            if environment.get("COYOTE_DEMO_MODE") != "docker":
                raise ValueError("Browser acceptance requires disposable Docker databases")


def _write_private(path: Path, value: dict[str, Any]) -> None:
    with open(path, "x", opener=lambda name, flags: os.open(name, flags, 0o600)) as stream:
        json.dump(value, stream, indent=2)
        stream.write("\n")


def _prepare_bundles(directory: Path) -> None:
    """Package only the synthetic starter's declared files for browser uploads."""
    directory.mkdir()
    starter = (
        ROOT / "services/demo/src/coyote_demo/data/clinical_workflows/starter/first_sample.yaml"
    )
    manifest = yaml.safe_load(starter.read_text())
    with zipfile.ZipFile(directory / "data.zip", "w", zipfile.ZIP_DEFLATED) as archive:
        for key, value in manifest.items():
            if isinstance(value, str) and value.startswith("../raw/"):
                source = (starter.parent / value).resolve()
                if not source.is_relative_to(starter.parent.parent / "raw"):
                    raise ValueError("Browser bundle must use only packaged synthetic files")
                archive.write(source, source.name)
                manifest[key] = source.name
    for name, sample_count in (("valid", 2), ("invalid", 3)):
        (directory / f"{name}.yaml").write_text(
            yaml.safe_dump(
                manifest | {"name": f"DEMO_BROWSER_{name.upper()}", "sample_no": sample_count}
            )
        )
    wgs = yaml.safe_load((starter.parent.parent / "manifests/demo_tumwgs.yaml").read_text())
    for key, value in wgs.items():
        if isinstance(value, str) and value.startswith("../raw/"):
            wgs[key] = Path(value).name
    (directory / "wgs.yaml").write_text(yaml.safe_dump(wgs | {"name": "DEMO_BROWSER_WGS"}))


def main(argv: list[str] | None = None) -> int:
    """Build, run and remove one synthetic test stack, retaining nonsecret evidence.

    Args:
        argv: Optional command-line arguments. No target URL, database URI or
            existing project can be supplied.

    Returns:
        Playwright's exit status, or an exception when setup/cleanup fails.

    Raises:
        ValueError: Output is outside the checkout, already used, or the stack is unsafe.
        RuntimeError: Docker, the build, startup or cleanup fails.
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, help="New evidence directory inside the checkout")
    args = parser.parse_args(argv)
    directory = (
        args.output or ROOT / ".cache" / f"browser-tests-{secrets.token_hex(6)}"
    ).absolute()
    if not directory.resolve().is_relative_to(ROOT) or directory.exists():
        raise ValueError("Choose a new browser evidence directory within the checkout")
    directory.mkdir(parents=True, mode=0o700)
    try:
        return _run(directory)
    finally:
        # Preflight and startup failures also erase credentials; evidence remains private.
        for name in ("settings.json", "compose.json", "browser.json", "demo.env"):
            (directory / "private" / name).unlink(missing_ok=True)


def _run(directory: Path) -> int:
    """Execute one fresh project; preserve evidence and clean up even on failed tests."""
    console = Console()
    # No deployment environment, Compose override, Docker context or proxy is inherited.
    clean = {key: os.environ[key] for key in ("PATH", "HOME", "LANG") if key in os.environ}
    runner = Runner(clean)
    with socket.socket() as reservation:
        reservation.bind(("127.0.0.1", 0))
        port = reservation.getsockname()[1]
    state = directory / "private"
    prepare(state, mode="docker", port=port)
    record = load_settings(state)
    environment = record["environment"] | record["compose"]
    runner.redactions.update(environment)
    project = record["compose"]["COYOTE_DEMO_PROJECT"]
    for resource in ("container", "network", "volume"):
        existing = runner.run(
            [
                *DOCKER,
                resource,
                "ls",
                "--quiet",
                "--filter",
                f"label=com.docker.compose.project={project}",
            ],
            label="Check fresh browser project",
            capture=True,
        )
        if existing.strip():
            raise ValueError("Generated browser project already exists; refusing to reuse it")
    configuration = json.loads(
        runner.run(
            [
                *DOCKER,
                "compose",
                "--env-file",
                "/dev/null",
                "--project-name",
                project,
                "--file",
                str(ROOT / "deploy/demo/compose.yml"),
                "config",
                "--format",
                "json",
            ],
            extra_env=environment,
            label="Resolve isolated browser configuration",
            capture=True,
        )
    )
    validate_stack(configuration, project, port)
    # Each run has its own image tags as well as its own containers and storage.
    for service in configuration["services"].values():
        image = service["image"]
        if image.startswith("coyote4-demo-"):
            service["image"] = image.replace("coyote4-demo-", project + "-", 1)
    compose_file = state / "compose.json"
    _write_private(compose_file, configuration)
    compose = [
        *DOCKER,
        "compose",
        "--env-file",
        "/dev/null",
        "--project-name",
        project,
        "--file",
        str(compose_file),
    ]
    started = time.time()
    exit_code = 1
    images = {}
    source_commit = runner.run(
        ["git", "rev-parse", "HEAD"], label="Record candidate source", capture=True
    ).strip()
    source_dirty = bool(
        runner.run(
            ["git", "status", "--porcelain", "--untracked-files=no"],
            label="Check candidate source changes",
            capture=True,
        ).strip()
    )
    try:
        console.log("Building and starting fresh synthetic browser services", "STEP")
        runner.run([*compose, "build"], label="Build disposable browser images")
        runner.run(
            [*compose, "up", "--no-build", "--detach", "--wait", "--wait-timeout", "240"],
            label="Start disposable browser stack",
        )
        containers = {}
        for service in ("frontend", "demo-mongo", "worker"):
            containers[service] = runner.run(
                [*compose, "ps", "--quiet", service],
                label="Identify owned test container",
                capture=True,
            ).strip()
        for service, identity in containers.items():
            images[service] = runner.run(
                [*DOCKER, "inspect", "--format", "{{.Image}}", identity],
                label="Record tested image identity",
                capture=True,
            ).strip()
        proof = state / "browser.json"
        _prepare_bundles(state / "bundles")
        _write_private(
            proof,
            {
                "format": 1,
                "project": project,
                "pid": os.getpid(),
                "created": time.time(),
                "baseURL": f"http://127.0.0.1:{port}/",
                "databases": DEMO_DATABASES,
                "containers": containers,
                "username": "coyote4.sysadmin",
                "password": environment["COYOTE_DEMO_ADMIN_PASSWORD"],
                "superuser": "coyote4.superuser",
                "superuserPassword": environment["COYOTE_DEMO_SUPERUSER_PASSWORD"],
                "reviewPassword": "Synthetic-9!" + secrets.token_urlsafe(32),
                "dnaSample": "DEMO_STARTER_DNA",
                "rnaSample": "DEMO_STARTER_RNA",
            },
        )
        console.log("Running browser acceptance against the owned disposable stack", "STEP")
        browser_env = clean | {
            "CI": "1",
            "PYTHON_BIN": sys.executable,
            "COYOTE4_E2E_STATE": str(proof),
            "PLAYWRIGHT_JSON_OUTPUT_NAME": str(directory / "browser-results.json"),
        }
        exit_code = subprocess.run(
            [
                "npm",
                "--prefix",
                "frontend",
                "run",
                "test:e2e:real",
                "--",
                "--workers=1",
                "--global-timeout=900000",
                "--output",
                str(directory / "artifacts"),
            ],
            cwd=ROOT,
            env=browser_env,
            check=False,
        ).returncode
        return exit_code
    finally:
        console.log("Removing this run's containers, network and disposable volumes", "STEP")
        try:
            logs = runner.run(
                [*compose, "logs", "--no-color"],
                label="Collect synthetic service logs",
                capture=True,
            )
            (directory / "services.log").write_text(redact(logs, environment))
        finally:
            runner.run(
                [*compose, "down", "--volumes", "--remove-orphans", "--rmi", "local"],
                label="Remove owned browser stack",
            )
            remaining = {}
            for resource in ("container", "network", "volume"):
                remaining[resource] = runner.run(
                    [
                        *DOCKER,
                        resource,
                        "ls",
                        "--quiet",
                        "--filter",
                        f"label=com.docker.compose.project={project}",
                    ],
                    label="Verify browser cleanup",
                    capture=True,
                ).split()
            _write_private(
                directory / "run.json",
                {
                    "project": project,
                    "started": started,
                    "finished": time.time(),
                    "browser_exit_code": exit_code,
                    "remaining_resources": remaining,
                    "databases": DEMO_DATABASES,
                    "synthetic_only": True,
                    "source_commit": source_commit,
                    "source_dirty": source_dirty
                    or bool(
                        runner.run(
                            ["git", "status", "--porcelain", "--untracked-files=no"],
                            label="Check source after browser acceptance",
                            capture=True,
                        ).strip()
                    ),
                    "images": images,
                },
            )
            if any(remaining.values()):
                raise RuntimeError("Disposable browser resource cleanup is incomplete")


if __name__ == "__main__":
    raise SystemExit(main())
