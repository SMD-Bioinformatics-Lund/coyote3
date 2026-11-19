# SPDX-FileCopyrightText: 2026 Ram Nanduri
# SPDX-License-Identifier: GPL-3.0-only

"""Manage MongoDB and Redis independently from application installation."""

from __future__ import annotations

import argparse
import re
from pathlib import Path

from .compose import Compose
from .config import ROOT, Profile, environment_name, native_environment
from .process import Console, Runner


class InfrastructureCompose(Compose):
    """Validate server credentials without requiring application secrets or an API service."""

    def validate(self) -> None:
        """Reject unrelated services and incomplete server configuration before startup."""
        services = self.config()["services"]
        if set(services) - {"mongo", "mongo_init", "mongo-kb", "mongo_kb_init", "redis"}:
            raise ValueError("Infrastructure commands accept MongoDB or Redis services only")
        for name, service in services.items():
            environment = service.get("environment") or {}
            required = (
                ("REDIS_PASSWORD",)
                if name == "redis"
                else ("MONGO_ROOT_USERNAME", "MONGO_ROOT_PASSWORD")
                if name.endswith("init")
                else (
                    "MONGO_INITDB_ROOT_USERNAME",
                    "MONGO_INITDB_ROOT_PASSWORD",
                    "MONGO_APP_USER",
                    "MONGO_APP_PASSWORD",
                )
            )
            for key in required:
                value = str(environment.get(key) or "")
                if not value or "CHANGE_ME" in value or "${" in value:
                    raise ValueError(f"{name}: set {key} in the server environment file")
                if "PASSWORD" in key and len(value) < 16:
                    raise ValueError(f"{name}: {key} must contain at least 16 characters")

    def prepare_storage(self) -> None:
        """Require provisioned server bind mounts; never create root-owned database storage."""
        for service in self.config()["services"].values():
            for mount in service.get("volumes", []):
                if mount.get("type") == "bind" and not Path(mount["source"]).exists():
                    raise ValueError(
                        f"Provision the server bind mount for {mount['target']} before startup"
                    )


def main(service: str, argv: list[str]) -> int:
    """Run one explicitly selected server lifecycle operation, preserving its data.

    Native mode controls a provisioned systemd service and never installs database
    software or changes its users. Docker mode uses the independent server Compose
    definitions, including the existing MongoDB replica-set initialization.
    """
    parser = argparse.ArgumentParser(prog=f"install.sh {service}", description=__doc__)
    parser.add_argument("operation", choices=("plan", "start", "stop", "restart", "status", "logs"))
    parser.add_argument("--mode", choices=("native", "docker"), required=True)
    parser.add_argument("--env-file", type=Path, required=True)
    parser.add_argument("--environment", type=environment_name)
    parser.add_argument("--project", help="Independent Docker project name")
    parser.add_argument(
        "--legacy", action="store_true", help="Use maintained older-host Docker runtime definitions"
    )
    parser.add_argument("--unit", help="Existing native systemd service name")
    parser.add_argument("--user", action="store_true", help="Use the native user's systemd manager")
    parser.add_argument(
        "--knowledgebase",
        action="store_true",
        help="Select the separate MongoDB knowledgebase server",
    )
    parser.add_argument(
        "--overlay", type=Path, action="append", help="Docker server overlay, for example Redis TLS"
    )
    args = parser.parse_args(argv)
    if args.knowledgebase and service != "mongo":
        parser.error("--knowledgebase applies only to MongoDB")
    if args.mode == "docker" and (args.unit or args.user):
        parser.error("--unit and --user apply only to native services")
    if args.mode == "native" and (args.project or args.overlay or args.legacy):
        parser.error("--project, --overlay and --legacy apply only to Docker services")
    environment = native_environment(args.env_file.resolve(strict=True))
    selected = environment_name(args.environment or environment.get("ENV_NAME", "production"))
    if (
        args.environment
        and environment.get("ENV_NAME")
        and selected != environment_name(environment["ENV_NAME"])
    ):
        raise ValueError("--environment disagrees with ENV_NAME")
    runner = Runner(environment)
    console = Console()
    if args.mode == "native":
        key = (
            "KNOWLEDGEBASE_MONGO_UNIT" if args.knowledgebase else f"COYOTE4_{service.upper()}_UNIT"
        )
        unit = args.unit or environment.get(key)
        if not unit or not re.fullmatch(r"[A-Za-z0-9_@.:-]+\.service", unit):
            raise ValueError(f"Select the provisioned native service with --unit or {key}")
        console.log(f"Native {service}: {args.operation} / {unit}")
        if args.operation == "plan":
            return 0
        user = ["--user"] if args.user else []
        if args.operation == "logs":
            command = ["journalctl", *user, "--unit", unit, "--lines=100", "--no-pager"]
        else:
            command = ["systemctl", *user, args.operation, "--", unit]
        runner.run(
            command,
            label=f"Native {service} {args.operation}; systemd access must already be provisioned",
        )
        return 0

    name = "mongo-kb" if args.knowledgebase else service
    folder = "legacy" if service == "mongo" and args.legacy else "compose"
    overlays = (
        [ROOT / "deploy/legacy/docker-compose.redis.yml"]
        if service == "redis" and args.legacy
        else []
    ) + (args.overlay or [])
    profile = Profile.load(
        args.env_file,
        environment=selected,
        project=args.project or f"coyote4-{selected}-{name}",
        files=[ROOT / "deploy" / folder / f"docker-compose.{service}.yml"],
        overlays=overlays,
        service_profiles=[name] if service == "mongo" else [],
        process_environment=environment,
    )
    console.log(f"Docker {name}: {args.operation} / {profile.project}")
    if args.operation == "plan":
        console.log("Plan only: no service connections or filesystem changes")
        return 0
    engine = InfrastructureCompose(profile, Runner(profile.process_env))
    if args.operation == "start":
        engine.validate()
        engine.run(["up", "-d", "--wait", "--wait-timeout", "180", name])
        if service == "mongo":
            initializer = "mongo_kb_init" if args.knowledgebase else "mongo_init"
            engine.run(["run", "--rm", "--no-deps", initializer])
    elif args.operation == "status":
        engine.run(["ps", name])
    elif args.operation == "logs":
        engine.run(["logs", "--tail=100", name])
    else:
        engine.run([args.operation, name])
    return 0
