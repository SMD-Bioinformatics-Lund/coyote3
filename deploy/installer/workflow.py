# SPDX-FileCopyrightText: 2026 Ram Nanduri
# SPDX-License-Identifier: GPL-3.0-only

"""Ordered installation with explicit checks before database writes and application startup."""

from __future__ import annotations

import stat
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlsplit

from scripts.release.verify_sdk_artifact import verify_compose_artifacts

from .compose import Compose
from .config import ROOT, STEPS, Profile
from .process import Console, Runner
from .storage import prepare


@dataclass(frozen=True)
class Options:
    """Operator-selected installation scope; omitted stages do not bypass startup checks."""

    steps: tuple[str, ...] = STEPS
    skip_build: bool = False
    skip_users: bool = False
    skip_application: bool = False
    skip_knowledgebase: bool = False
    with_knowledgebase_indexes: bool = False
    identity_maintenance_uri_file: Path | None = None
    knowledgebase_maintenance_uri_file: Path | None = None
    sys_admin_username: str | None = None
    sys_admin_email: str | None = None
    username: str | None = None
    email: str | None = None

    def validate(self) -> None:
        """Reject contradictory selections before any service is contacted."""
        if (
            not self.steps
            or set(self.steps) - set(STEPS)
            or len(set(self.steps)) != len(self.steps)
        ):
            raise ValueError("Invalid or repeated --steps selection")
        if self.skip_users and not (self.skip_application and self.skip_knowledgebase):
            raise ValueError("--skip-users requires --skip-application --skip-knowledgebase")
        if self.identity_maintenance_uri_file and not set(self.steps) & {
            "validate",
            "bootstrap",
            "indexes",
            "start",
        }:
            raise ValueError(
                "Identity role upgrade requires validation, bootstrap, indexes or startup"
            )
        if (
            self.knowledgebase_maintenance_uri_file
            and self.skip_knowledgebase
            and not self.with_knowledgebase_indexes
        ):
            raise ValueError(
                "Maintenance URI override requires knowledgebase installation or indexes"
            )


@dataclass(frozen=True)
class Target:
    """Nonsecret installation values resolved from Compose."""

    network: str
    application_db: str
    identity_db: str
    public_url: str
    local_url: str

    @classmethod
    def from_config(cls, config: dict) -> Target:
        """Reject invalid network and proxy selections before using a deployment target."""
        network = config["networks"]["app"]
        if network.get("external") is not True:
            raise ValueError(
                "Application network must be external and provisioned before installation"
            )
        env = config["services"]["api"]["environment"]
        prefix = (env.get("SCRIPT_NAME") or "").rstrip("/")
        if prefix and (not prefix.startswith("/") or any(char in prefix for char in "?#\r\n")):
            raise ValueError("SCRIPT_NAME must be an absolute URL path without a query or fragment")
        public = urlsplit(env.get("PUBLIC_BASE_URL") or "")
        if (
            public.scheme not in {"http", "https"}
            or not public.hostname
            or public.path not in {"", "/"}
            or public.query
            or public.fragment
            or public.username
            or public.password
        ):
            raise ValueError(
                "PUBLIC_BASE_URL must be an http(s) origin; put the application prefix in SCRIPT_NAME"
            )
        ports = [
            port
            for port in config["services"]["proxy"].get("ports", [])
            if int(port["target"]) == 8088 and port.get("protocol", "tcp") == "tcp"
        ]
        if not ports or not ports[0].get("published"):
            raise ValueError("Proxy HTTP port 8088 must have a published host port")
        port = ports[0]
        host = port.get("host_ip") or "127.0.0.1"
        host = {"0.0.0.0": "127.0.0.1", "::": "::1"}.get(host, host)
        if ":" in host:
            host = f"[{host}]"
        values = [
            network["name"],
            env["COYOTE4_DB"],
            env["IDENTITY_DB"],
            env["PUBLIC_BASE_URL"].rstrip("/") + prefix,
            f"http://{host}:{int(port['published'])}{prefix}",
        ]
        if any(
            not isinstance(value, str) or not value or "\n" in value or "\r" in value
            for value in values
        ):
            raise ValueError("Invalid installation settings")
        return cls(*values)


def private_uri(path: Path) -> str:
    """Read one explicitly selected owner-only credential file without following symlinks."""
    metadata = path.lstat()
    if not stat.S_ISREG(metadata.st_mode) or metadata.st_mode & 0o077:
        raise ValueError("Maintenance credentials must be in an owner-only regular file")
    value = path.read_text().strip()
    if not value or "\n" in value or "\r" in value:
        raise ValueError("Maintenance URI file must contain one nonempty URI")
    return value


class Installer:
    """Build, validate and start a selected installation without resetting existing data."""

    def __init__(
        self,
        profile: Profile,
        options: Options,
        *,
        console: Console | None = None,
        runner: Runner | None = None,
    ) -> None:
        self.profile = profile
        self.options = options
        self.console = console or Console()
        self.runner = runner or Runner(profile.process_env)
        self.compose = Compose(profile, self.runner)

    def plan(self) -> None:
        """Describe selected stages using local metadata only; perform no writes or subprocesses."""
        self.options.validate()
        self.profile.validate()
        self.console.log(
            f"Environment: {self.profile.environment}; project: {self.profile.project}; image: {self.profile.process_env['COYOTE4_IMAGE_TAG']}"
        )
        for path in self.profile.files:
            self.console.log(
                f"Compose: {path.relative_to(ROOT) if path.is_relative_to(ROOT) else path.name}"
            )
        selected = [
            step
            for step in STEPS
            if step in self.options.steps and not (step == "build" and self.options.skip_build)
        ]
        self.console.log("Stages: " + " → ".join(selected))
        self.console.log(
            "Existing databases are preserved. Partial installations and index conflicts stop deployment."
        )
        self.console.log("Plan only: no Docker, service connections or filesystem changes.")

    def _check(
        self, name: str, *arguments: str, capture: bool = False, maintenance: str = ""
    ) -> str:
        return self._container(
            ["python3", "-m", "deploy.installer.checks", name, *arguments],
            capture=capture,
            maintenance=maintenance,
        )

    def _container(
        self, arguments: list[str], *, capture: bool = False, maintenance: str = ""
    ) -> str:
        options = ["-e", "KNOWLEDGEBASE_MONGO_URI"] if maintenance else []
        extra = {"KNOWLEDGEBASE_MONGO_URI": maintenance} if maintenance else {}
        return self.compose.run(
            ["run", "--rm", "--no-deps", "-T", *options, "api", *arguments],
            capture=capture,
            extra_env=extra,
        )

    def run(self) -> None:
        """Execute selected stages in order, preserving required gates and stopping on failure."""
        self.options.validate()
        self.profile.validate()
        options = self.options
        selected = set(options.steps)
        identity_uri = (
            private_uri(options.identity_maintenance_uri_file)
            if options.identity_maintenance_uri_file
            else ""
        )
        knowledge_uri = (
            private_uri(options.knowledgebase_maintenance_uri_file)
            if options.knowledgebase_maintenance_uri_file
            else ""
        )
        self.console.log(
            f"Coyote4 installation — {self.profile.environment} / {self.profile.project}"
        )
        if not self.runner.environment.get("GIT_COMMIT"):
            self.runner.environment["GIT_COMMIT"] = self.runner.run(
                ["git", "rev-parse", "HEAD"], label="Source revision", capture=True
            ).strip()
        config = self.compose.config()
        self.compose.validate()
        target = Target.from_config(config)
        if "build" in selected and not options.skip_build:
            verify_compose_artifacts(config, ROOT / "release.toml")
        if (
            selected & {"network", "validate", "bootstrap", "indexes", "start"}
            or options.with_knowledgebase_indexes
            or knowledge_uri
        ):
            self.console.log("Checking the provisioned application bridge", "STEP")
            driver = self.runner.run(
                ["docker", "network", "inspect", target.network, "--format", "{{.Driver}}"],
                label="External network inspection (provision the bridge first)",
                capture=True,
            ).strip()
            if driver != "bridge":
                raise ValueError(
                    "Application network must use the bridge driver; no networking changes were attempted"
                )
        if "directories" in selected:
            self.console.log("Preparing application storage", "STEP")
            prepare(config)
        if "build" in selected and not options.skip_build:
            self.console.log("Building versioned application images", "STEP")
            self.compose.run(["build"])
        if "start" in selected:
            self.console.log("Checking Redis connectivity from the API container", "STEP")
            self.compose.run(
                ["up", "-d", "--no-deps", "--no-build", "--wait", "--wait-timeout", "60", "redis"]
            )
            self._check("redis")
        state = "unchecked"
        if selected & {"validate", "bootstrap", "indexes", "start"}:
            self.console.log(
                "Validating configuration, database access and installation state", "STEP"
            )
            if identity_uri:
                self.compose.run(
                    [
                        "run",
                        "--rm",
                        "--no-deps",
                        "-T",
                        "-e",
                        "COYOTE_INSTALL_IDENTITY_URI",
                        "api",
                        "python3",
                        "-m",
                        "scripts.database.manage_mongo_roles",
                        "--maintenance-uri-env",
                        "COYOTE_INSTALL_IDENTITY_URI",
                        "--apply",
                    ],
                    extra_env={"COYOTE_INSTALL_IDENTITY_URI": identity_uri},
                )
            self._check("configuration")
            output = self._check("state", capture=True).strip().splitlines()
            state = output[-1] if output else ""
            if state not in {"fresh", "existing"}:
                raise ValueError("Unrecognized target state; stopping before bootstrap")
        if knowledge_uri:
            self.compose.run(
                [
                    "run",
                    "--rm",
                    "--no-deps",
                    "-T",
                    "-e",
                    "COYOTE_INSTALL_KB_URI",
                    "api",
                    "python3",
                    "-m",
                    "deploy.installer.checks",
                    "maintenance",
                ],
                extra_env={"COYOTE_INSTALL_KB_URI": knowledge_uri},
            )
        if "bootstrap" in selected:
            if state == "fresh":
                self.console.log(
                    "Installing factory records into the verified empty target", "STEP"
                )
                arguments = [
                    "python3",
                    "scripts/bootstrap/bootstrap_database.py",
                    "--require-empty-target",
                    "--db",
                    target.application_db,
                    "--identity-db",
                    target.identity_db,
                ]
                for name in ("sys_admin_username", "sys_admin_email", "username", "email"):
                    if value := getattr(options, name):
                        arguments.extend(["--" + name.replace("_", "-"), value])
                for name in ("skip_users", "skip_application", "skip_knowledgebase"):
                    if getattr(options, name):
                        arguments.append("--" + name.replace("_", "-"))
                self._container(arguments, maintenance=knowledge_uri)
                if not options.skip_users:
                    state = "existing"
            else:
                self.console.log(
                    "Existing deployment: factory bootstrap skipped; accounts and data preserved"
                )
        if "indexes" in selected:
            self.console.log("Checking and applying application and identity indexes", "STEP")
            self._indexes()
        if options.with_knowledgebase_indexes:
            self.console.log("Checking and applying knowledgebase indexes", "STEP")
            self._indexes(knowledge_uri, "knowledgebase")
        if "start" in selected:
            if state != "existing" and not options.skip_users:
                raise ValueError("Initial accounts are missing; run bootstrap first")
            if "indexes" not in selected:
                self._check("indexes-ready")
            self.console.log("Starting services and waiting for container health", "STEP")
            self.compose.run(["up", "-d", "--no-build", "--wait", "--wait-timeout", "180"])
            self.compose.run(["ps"])
        if "health" in selected:
            self.console.log("Checking the API and frontend through the published proxy", "STEP")
            self.runner.run(
                [
                    "curl",
                    "--fail",
                    "--show-error",
                    "--retry",
                    "6",
                    "--retry-connrefused",
                    "--retry-delay",
                    "2",
                    "--max-time",
                    "15",
                    target.local_url + "/api/v1/health",
                ],
                label="API health check",
            )
            self.runner.run(
                [
                    "curl",
                    "--fail",
                    "--show-error",
                    "--output",
                    "/dev/null",
                    "--max-time",
                    "15",
                    target.local_url + "/",
                ],
                label="Frontend health check",
            )
            self.console.log(f"Local application (published proxy port): {target.local_url}/")
            self.console.log(f"Public application (PUBLIC_BASE_URL): {target.public_url}/")
        self.console.complete()

    def _indexes(self, maintenance: str = "", scope: str = "") -> None:
        arguments = ["--scope", scope] if scope else []
        self._check("indexes", *arguments, maintenance=maintenance)
        self._container(
            [
                "python3",
                "scripts/database/manage_mongo_indexes.py",
                "apply",
                *arguments,
                "--summary",
            ],
            maintenance=maintenance,
        )
        self._check("indexes-ready", *arguments, maintenance=maintenance)
