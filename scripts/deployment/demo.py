#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Ram Nanduri
# SPDX-License-Identifier: GPL-3.0-only

"""Prepare and run an explicitly selected, isolated local Coyote demonstration."""

from __future__ import annotations

import argparse
import base64
import json
import os
import re
import secrets
import subprocess
import sys
from pathlib import Path
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[2]


def _private_text(path: Path) -> str:
    """Read an explicitly selected owner-only credential file.

    Args:
        path: Plain text file containing one URI, without shell expansion.

    Returns:
        Stripped credential text.

    Raises:
        ValueError: The file is a symlink, group/world-readable or multiline.
    """
    if path.is_symlink() or path.stat().st_mode & 0o077:
        raise ValueError("Credential files must be owner-only regular files")
    value = path.read_text().strip()
    if not value or "\n" in value or "\r" in value:
        raise ValueError("Credential files must contain exactly one URI")
    return value


def prepare(directory: Path, *, mode: str, port: int, mongo: str = "", redis: str = "") -> Path:
    """Create new demo settings without reading deployment files or ambient secrets.

    Args:
        directory: New, empty state directory owned by the invoking operator.
        mode: Docker-managed services or explicitly provided native local services.
        port: Loopback browser port; native API uses the following port.
        mongo: Explicit restricted-user replica-set URI for native mode only.
        redis: Explicit authenticated dedicated Redis URL for native mode only.

    Returns:
        Path to the generated private settings record.

    Raises:
        ValueError: Targets fail demo isolation checks, the port is invalid or
            the directory contains files. Existing settings are never overwritten.
    """
    from coyote_demo.deployment import DEMO_DATABASES, DEMO_MONGO_URI_KEYS, validate_demo_target

    directory = directory.expanduser().absolute()
    if not 1024 <= port <= 65534:
        raise ValueError("Choose a demo port between 1024 and 65534")
    if directory.is_symlink() or (directory.exists() and any(directory.iterdir())):
        raise ValueError("Demo state directory must be new or empty")
    mongo_password = secrets.token_hex(32)
    redis_password = secrets.token_hex(32)
    if mode == "docker":
        mongo = (
            f"mongodb://coyote_demo:{mongo_password}@demo-mongo:27017/"
            "?authSource=admin&replicaSet=coyote-demo-rs&directConnection=true"
        )
        redis = f"redis://default:{redis_password}@demo-redis:6379"
    elif mode != "native" or not mongo or not redis:
        raise ValueError("Native mode requires explicit MongoDB and Redis credential files")
    redis_endpoint = urlsplit(redis)
    if redis_endpoint.path not in {"", "/"} or redis_endpoint.query or redis_endpoint.fragment:
        raise ValueError("Native Redis input must omit database number and query parameters")
    environment = {
        **DEMO_DATABASES,
        **dict.fromkeys(DEMO_MONGO_URI_KEYS, mongo),
        "COYOTE_DEMO_ENABLED": "1",
        "COYOTE_DEMO_MODE": mode,
        "ENV_NAME": "testing",
        "COYOTE4_RUNTIME_MODE": "production",
        "TESTING": "0",
        "DEVELOPMENT": "0",
        "AUTHENTICATION_PROVIDERS": "local",
        "LDAP_HOST": "",
        "SMTP_HOST": "",
        "GENS_URI": "",
        "IGV_URI": "",
        "ONCOKB_PUBLIC_LOOKUPS_ENABLED": "0",
        "CLINPGX_PUBLIC_LOOKUPS_ENABLED": "0",
        "COYOTE4_INGEST_WATCH_ENABLED": "0",
        "CACHE_REQUIRED": "1",
        "CACHE_REDIS_URL": f"{redis.rstrip('/')}/0",
        "CELERY_BROKER_URL": f"{redis.rstrip('/')}/1",
        "CELERY_RESULT_BACKEND": f"{redis.rstrip('/')}/2",
        "SECRET_KEY": secrets.token_hex(32),
        "INTERNAL_API_TOKEN": secrets.token_hex(32),
        "PASSWORD_TOKEN_SALT": secrets.token_hex(32),
        "COYOTE_DEMO_ADMIN_PASSWORD": secrets.token_urlsafe(24),
        "COYOTE_DEMO_SUPERUSER_PASSWORD": secrets.token_urlsafe(24),
        "ORGANIZATION_NAME": "Coyote4 demonstration — synthetic data",
        "PUBLIC_BASE_URL": f"http://127.0.0.1:{port}",
        "SCRIPT_NAME": "",
        "API_CSRF_ENABLED": "1",
        "API_RATE_LIMIT_ENABLED": "1",
        "LOG_FILE_ENABLED": "0",
        "LOG_ROOT": "/app/logs" if mode == "docker" else str(directory / "logs"),
        "COYOTE4_RUNTIME_ROOT": "/app" if mode == "docker" else str(directory / "runtime"),
        "COYOTE4_DATA_ROOT": "/data" if mode == "docker" else str(directory / "data"),
        "PYTHONDONTWRITEBYTECODE": "1",
        "PYTHONUNBUFFERED": "1",
    }
    validate_demo_target(environment)
    compose = {
        "COYOTE_DEMO_PROJECT": f"coyote4-demo-{secrets.token_hex(4)}",
        "COYOTE_DEMO_PORT": str(port),
        "COYOTE_DEMO_MONGO_PASSWORD": mongo_password,
        "COYOTE_DEMO_MONGO_ROOT_PASSWORD": secrets.token_hex(32),
        "COYOTE_DEMO_MONGO_KEY": base64.b64encode(secrets.token_bytes(96)).decode(),
        "COYOTE_DEMO_REDIS_PASSWORD": redis_password,
    }
    directory.mkdir(mode=0o700, parents=True, exist_ok=True)
    directory.chmod(0o700)
    for name in ("runtime", "data", "logs"):
        (directory / name).mkdir(mode=0o700)
    record = {"environment": environment, "compose": compose, "port": port, "format": 1}
    path = directory / "settings.json"
    with open(path, "x", opener=lambda name, flags: os.open(name, flags, 0o600)) as output:
        json.dump(record, output, indent=2)
        output.write("\n")
    with open(
        directory / "demo.env", "x", opener=lambda name, flags: os.open(name, flags, 0o600)
    ) as output:
        for key, value in (environment | compose).items():
            output.write(f"{key}={json.dumps(value, ensure_ascii=False)}\n")
    return path


def load_settings(directory: Path) -> dict:
    """Read a generated state record and revalidate its targets before execution.

    Args:
        directory: Explicit state directory created by prepare.

    Returns:
        Validated environment, project identity and browser port.

    Raises:
        ValueError: The record is unsafe, uses another format or has an ambient .env file.
    """
    from coyote_demo.deployment import validate_demo_target

    path = directory / "settings.json"
    if path.is_symlink() or path.stat().st_mode & 0o077:
        raise ValueError("Demo settings must remain owner-only")
    record = json.loads(path.read_text())
    if record.get("format") != 1:
        raise ValueError("Unsupported demo settings format")
    if not re.fullmatch(r"coyote4-demo-[a-f0-9]{8}", record["compose"]["COYOTE_DEMO_PROJECT"]):
        raise ValueError("Demo project identity must use its generated isolated name")
    validate_demo_target(record["environment"])
    runtime = Path(record["environment"]["COYOTE4_RUNTIME_ROOT"])
    if record["environment"]["COYOTE_DEMO_MODE"] == "native":
        if runtime != directory / "runtime" or (runtime / ".env").exists():
            raise ValueError("Native demo must use its isolated runtime directory without .env")
        if Path(record["environment"]["COYOTE4_DATA_ROOT"]) != directory / "data":
            raise ValueError("Native demo must use its isolated data directory")
    return record


def main(argv: list[str] | None = None) -> int:
    """Prepare settings or invoke one fixed local deployment operation.

    Args:
        argv: Explicit arguments for tests, or None for the operator's command line.

    Returns:
        Zero after preparation or the selected process's exit status.

    Raises:
        ValueError: Settings are unsafe or an operation does not match the prepared mode.
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--directory", type=Path, required=True)
    commands = parser.add_subparsers(dest="operation", required=True)
    preparation = commands.add_parser("prepare")
    preparation.add_argument("--mode", choices=["docker", "native"], required=True)
    preparation.add_argument("--port", type=int, default=8089)
    preparation.add_argument("--mongo-uri-file", type=Path)
    preparation.add_argument("--redis-url-file", type=Path)
    compose_parser = commands.add_parser("compose")
    compose_parser.add_argument("command", choices=["config", "build", "up", "stop", "ps", "logs"])
    native_parser = commands.add_parser("run")
    native_parser.add_argument(
        "service", choices=["bootstrap", "api", "frontend", "worker", "maintenance-worker", "beat"]
    )
    args = parser.parse_args(argv)
    directory = args.directory.expanduser().absolute()
    if args.operation == "prepare":
        path = prepare(
            directory,
            mode=args.mode,
            port=args.port,
            mongo=_private_text(args.mongo_uri_file) if args.mongo_uri_file else "",
            redis=_private_text(args.redis_url_file) if args.redis_url_file else "",
        )
        print(f"Created private demo settings: {path}")
        print("No services were started and no database was accessed.")
        return 0
    record = load_settings(directory)
    clean = {key: os.environ[key] for key in ("PATH", "HOME", "LANG") if key in os.environ}
    mode = record["environment"]["COYOTE_DEMO_MODE"]
    if args.operation == "compose":
        if mode != "docker":
            raise ValueError("Compose requires Docker demo settings")
        # All interpolation values come from the validated record, not the caller's
        # environment, project .env file, Docker context or normal deployment files.
        clean.update(record["environment"] | record["compose"])
        command = [
            "docker",
            "--host",
            "unix:///var/run/docker.sock",
            "compose",
            "--env-file",
            "/dev/null",
            "--project-name",
            record["compose"]["COYOTE_DEMO_PROJECT"],
            "--file",
            str(ROOT / "deploy/demo/compose.yml"),
            args.command,
        ]
        if args.command == "up":
            command.extend(["--build", "--detach"])
        elif args.command == "config":
            command.append("--quiet")
        return subprocess.run(command, env=clean, cwd=directory, check=False).returncode
    if mode != "native":
        raise ValueError("Native commands require native demo settings")
    clean.update(record["environment"])
    port = record["port"]
    commands = {
        "bootstrap": [sys.executable, str(ROOT / "scripts/deployment/demo_bootstrap.py")],
        "api": [
            sys.executable,
            "-m",
            "uvicorn",
            "coyote_api.app.main:app",
            "--host",
            "127.0.0.1",
            "--port",
            str(port + 1),
        ],
        "frontend": [
            "npm",
            "--prefix",
            str(ROOT / "frontend"),
            "run",
            "dev",
            "--",
            "--host",
            "127.0.0.1",
            "--port",
            str(port),
            "--strictPort",
        ],
        "worker": [
            sys.executable,
            "-m",
            "coyote_demo.runtime",
            "ingest",
            "--concurrency=1",
        ],
        "maintenance-worker": [
            sys.executable,
            "-m",
            "coyote_demo.runtime",
            "maintenance",
            "--concurrency=1",
        ],
        "beat": [sys.executable, "-m", "coyote_demo.runtime", "beat"],
    }
    clean["COYOTE4_API_INTERNAL_URL"] = f"http://127.0.0.1:{port + 1}"
    return subprocess.run(
        commands[args.service], env=clean, cwd=directory / "runtime", check=False
    ).returncode


if __name__ == "__main__":
    raise SystemExit(main())
