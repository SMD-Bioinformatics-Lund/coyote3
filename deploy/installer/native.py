# SPDX-FileCopyrightText: 2026 Ram Nanduri
# SPDX-License-Identifier: GPL-3.0-only

"""Install the application natively while keeping MongoDB and Redis independently managed."""

from __future__ import annotations

import json
import re
import shutil
import socket
import sys
from pathlib import Path

from .config import ROOT, Profile
from .development import DevelopmentWatcher
from .native_services import (
    UserServices,
    operation_lock,
    prepare_directory,
    private_write,
    write_environment,
)
from .process import Console, Runner
from .workflow import Installer, Options, Target, private_uri

PORT_DEFAULTS = {"api": 8001, "frontend": 3000, "docs": 8080, "monitor": 5514, "proxy": 6801}
PUBLIC_SETTINGS = frozenset(
    {
        "PATH",
        "HOME",
        "USER",
        "LOGNAME",
        "LANG",
        "LC_ALL",
        "PWD",
        "SSL_CERT_FILE",
        "SSL_CERT_DIR",
        "ENV_NAME",
        "SCRIPT_NAME",
        "PUBLIC_BASE_URL",
        "ORGANIZATION_NAME",
        "LOCAL_TIME_ZONE",
        "TZ",
        "GENS_URI",
        "IGV_URI",
        "IGV_DATA_ROOT",
        "COYOTE4_API_INTERNAL_URL",
        "CHOKIDAR_USEPOLLING",
    }
)


class NativeInstaller(Installer):
    """Use the application installation gates with a private venv and user services.

    MongoDB and Redis are never started or stopped here. The selected file supplies
    their endpoints, whether those servers are native processes or containers.
    """

    def __init__(
        self,
        profile: Profile,
        options: Options,
        *,
        console: Console | None = None,
        runner: Runner | None = None,
    ) -> None:
        self.profile, self.options = profile, options
        self.console = console or Console()
        if profile.directory is None:
            raise ValueError("Native deployment requires a runtime directory")
        self.directory = profile.directory
        if any(char in str(path) for path in (self.directory, ROOT) for char in '\n\r"$;{}%'):
            raise ValueError(
                "Native workspace/runtime paths contain unsupported service configuration characters"
            )
        self.environment = dict(profile.process_env)
        self.environment.setdefault("COYOTE4_RUNTIME_ROOT", str(self.directory / "runtime"))
        self.environment.setdefault("COYOTE4_DATA_ROOT", str(self.directory / "data"))
        self.environment.setdefault("LOG_ROOT", str(self.directory / "logs"))
        self.environment["PYTHONDONTWRITEBYTECODE"] = "1"
        self.environment["PYTHONUNBUFFERED"] = "1"
        self.environment["COYOTE4_MONITOR_HOST"] = "127.0.0.1"
        self.environment["PYTHONPATH"] = str(ROOT)
        self.ports = {
            name: int(
                self.environment.get(
                    {"proxy": "COYOTE4_PORT", "monitor": "COYOTE4_MONITOR_PORT"}.get(
                        name, f"COYOTE4_NATIVE_{name.upper()}_PORT"
                    ),
                    default,
                )
            )
            for name, default in PORT_DEFAULTS.items()
        }
        if any(not 1024 <= port <= 65535 for port in self.ports.values()) or len(
            set(self.ports.values())
        ) != len(self.ports):
            raise ValueError("Native services require distinct, unprivileged ports (1024–65535)")
        self.environment["COYOTE4_MONITOR_PORT"] = str(self.ports["monitor"])
        self.python = str(self.directory / "venv/bin/python")
        self.runner = runner or Runner(self.environment)
        self.runner.redactions.update(self.environment)
        self.services = UserServices(profile.project, self.directory, self.runner)
        self.target = Target.from_settings(
            self.environment, local_origin=f"http://127.0.0.1:{self.ports['proxy']}"
        )

    def commands(self) -> dict[str, list[str]]:
        """Describe native application processes without starting them."""
        bin_dir = self.directory / "venv/bin"
        celery = [str(bin_dir / "celery"), "-A", "coyote_api.celery_app:celery_app"]
        level = self.environment.get("CELERY_LOG_LEVEL", "INFO")
        commands = {
            "monitor": [self.python, "-m", "coyote_api.app.monitor"],
            "api": [
                self.python,
                "-m",
                "uvicorn",
                "coyote_api.app.main:app",
                "--host",
                "127.0.0.1",
                "--port",
                str(self.ports["api"]),
            ],
            "worker": [
                str(bin_dir / "coyote-relay-worker"),
                f"--hostname={self.profile.project}-ingest@localhost",
                f"--loglevel={level}",
                "--queues=ingest",
                f"--concurrency={self.environment.get('CELERY_WORKER_CONCURRENCY', '2')}",
            ],
            "maintenance-worker": [
                *celery,
                "worker",
                f"--hostname={self.profile.project}-maintenance@localhost",
                f"--loglevel={level}",
                "--queues=default",
                f"--concurrency={self.environment.get('CELERY_MAINTENANCE_CONCURRENCY', '2')}",
            ],
            "beat": [
                *celery,
                "beat",
                f"--loglevel={level}",
                "--pidfile",
                str(self.directory / "beat.pid"),
                "--schedule",
                str(self.directory / "beat-schedule"),
            ],
        }
        for name in ("api", "worker", "maintenance-worker", "beat"):
            role = "worker" if name == "maintenance-worker" else name
            commands[name] = [
                self.python,
                "-m",
                "coyote_api.infra.observability.run_service",
                role,
                *commands[name],
            ]
        if self.profile.environment == "dev":
            watcher = DevelopmentWatcher(ROOT, self.environment)
            for name, command in commands.items():
                commands[name] = watcher.command(command, [])
                commands[name][0] = self.python
            commands["frontend"] = [
                "npm",
                "--prefix",
                str(ROOT / "frontend"),
                "run",
                "dev",
                "--",
                "--host",
                "127.0.0.1",
                "--port",
                str(self.ports["frontend"]),
            ]
        commands["proxy"] = [
            "nginx",
            "-p",
            str(self.directory) + "/",
            "-c",
            str(self.directory / "nginx.conf"),
            "-g",
            "daemon off;",
        ]
        return commands

    def public_environment(self) -> dict[str, str]:
        """Limit frontend builds and web processes to public UI settings and tool paths."""
        return {key: value for key, value in self.environment.items() if key in PUBLIC_SETTINGS}

    def plan(self) -> None:
        self.options.validate()
        self.profile.validate()
        self.console.log(
            f"Native application: {self.profile.project}; environment: {self.profile.environment}"
        )
        self.console.log("Services: " + ", ".join(self.commands()))
        self.console.log(
            "MongoDB and Redis are external dependencies; their lifecycle is unchanged"
        )
        self.console.log("Plan only: no processes, service connections or filesystem changes")

    def _execute(
        self,
        arguments: list[str],
        *,
        capture: bool = False,
        maintenance: str = "",
        extra_env: dict[str, str] | None = None,
    ) -> str:
        extra = dict(extra_env or {})
        if maintenance:
            extra["KNOWLEDGEBASE_MONGO_URI"] = maintenance
        return self.runner.run(
            [self.python, *arguments],
            label="Native application installation check",
            capture=capture,
            extra_env=extra,
        )

    def _prepare(self) -> None:
        """Create private runtime state and retain existing application data."""
        prepare_directory(self.directory)
        for key in ("COYOTE4_RUNTIME_ROOT", "COYOTE4_DATA_ROOT", "LOG_ROOT"):
            path = Path(self.environment[key])
            if not path.is_absolute():
                raise ValueError(f"{key} must be an absolute native path")
            prepare_directory(path)
        runtime = Path(self.environment["COYOTE4_RUNTIME_ROOT"])
        if (runtime / ".env").exists():
            raise ValueError("Native runtime must not contain a second .env file; use --env-file")
        for name in ("frontend-nginx", "nginx-temp", "docs", "frontend"):
            prepare_directory(self.directory / name)
        metadata = self.directory / "installation.json"
        if metadata.is_symlink():
            raise ValueError("Native installation metadata must not be a symbolic link")
        record = {
            "workspace": str(ROOT),
            "project": self.profile.project,
            "environment": self.profile.environment,
        }
        if metadata.exists() and json.loads(metadata.read_text()) != record:
            raise ValueError("Native state belongs to a different installation")
        private_write(metadata, json.dumps(record) + "\n")

    def _build(self) -> None:
        self.console.log(
            "Installing the locked application into its native virtual environment", "STEP"
        )
        command = [
            "uv",
            "sync",
            "--frozen",
            "--all-packages",
            "--no-install-package",
            "coyote-demo",
            "--no-default-groups",
            "--group",
            "application",
            "--group",
            "docs",
            "--python",
            sys.executable,
        ]
        command.extend(
            ["--group", "watch"] if self.profile.environment == "dev" else ["--no-editable"]
        )
        self.runner.run(
            command,
            label="Native Python installation",
            extra_env={"UV_PROJECT_ENVIRONMENT": str(self.directory / "venv")},
        )
        self.runner.run(
            ["npm", "--prefix", "frontend", "ci"],
            label="Frontend dependencies",
            process_env=self.public_environment(),
        )
        if self.profile.environment != "dev":
            self.runner.run(
                [
                    "npm",
                    "--prefix",
                    "frontend",
                    "run",
                    "build",
                    "--",
                    "--outDir",
                    str(self.directory / "frontend"),
                ],
                label="Frontend build",
                process_env=self.public_environment(),
            )
        self.runner.run(
            [
                str(self.directory / "venv/bin/mkdocs"),
                "build",
                "--strict",
                "--site-dir",
                str(self.directory / "docs"),
            ],
            label="Documentation build",
        )

    def _web_configuration(self) -> None:
        """Reuse the Docker web configuration and security headers for native Nginx."""
        prefix = self.environment.get("SCRIPT_NAME", "").rstrip("/")
        if prefix and not re.fullmatch(r"(?:/[A-Za-z0-9_-]+)+", prefix):
            raise ValueError(
                "Native SCRIPT_NAME must contain URL path segments using letters, digits, underscores or hyphens"
            )
        # Runtime paths are quoted in Nginx and must not contain configuration tokens.
        if any(char in str(self.directory) for char in '\n\r"$;{}%'):
            raise ValueError("Native directory contains unsupported Nginx path characters")
        ports = self.ports
        syslog = f"127.0.0.1:{ports['monitor']}"
        environment = {
            "COYOTE4_SYSLOG_TARGET": syslog,
            "COYOTE4_NGINX_OUTPUT_PATH": str(self.directory / "proxy.conf"),
            "COYOTE4_NGINX_FRONTEND_UPSTREAM": f"http://127.0.0.1:{ports['frontend']}",
            "COYOTE4_NGINX_API_UPSTREAM": f"http://127.0.0.1:{ports['api']}",
            "COYOTE4_NGINX_DOCS_UPSTREAM": f"http://127.0.0.1:{ports['docs']}",
            "COYOTE4_NGINX_LISTEN": f"127.0.0.1:{ports['proxy']}",
            "COYOTE4_NGINX_RESOLVER": "127.0.0.1",
            "COYOTE4_NGINX_ERROR_PAGE": str(
                ROOT / "deploy/compose/nginx/error-pages/unavailable.html"
            ),
            "COYOTE4_FRONTEND_NGINX_DIRECTORY": str(self.directory / "frontend-nginx"),
            "COYOTE4_FRONTEND_ROOT": str(self.directory / "frontend"),
            "COYOTE4_FRONTEND_LISTEN": f"127.0.0.1:{ports['frontend']}",
        }
        self.runner.run(
            ["sh", "deploy/compose/nginx/render-config.sh"],
            label="Native reverse proxy configuration",
            extra_env=environment,
        )
        includes = [self.directory / "proxy.conf"]
        if self.profile.environment != "dev":
            self.runner.run(
                ["sh", "docker/nginx/render-frontend-config.sh"],
                label="Native frontend configuration",
                extra_env=environment,
            )
            includes.extend(
                [
                    self.directory / "frontend-nginx/default.conf",
                    self.directory / "frontend-nginx/frontend-compression.conf",
                    self.directory / "frontend-nginx/observability.conf",
                ]
            )
        docs = (
            (ROOT / "docker/nginx/docs.conf")
            .read_text()
            .replace("monitor:5514", syslog)
            .replace("listen 8080;", f"listen 127.0.0.1:{ports['docs']};")
            .replace("root /usr/share/nginx/html;", f'root "{self.directory / "docs"}";')
        )
        private_write(self.directory / "docs.conf", docs)
        includes.append(self.directory / "docs.conf")
        include_text = "\n".join(f'    include "{path}";' for path in includes)
        private_write(
            self.directory / "nginx.conf",
            f'''worker_processes 1;
pid "{self.directory / "nginx.pid"}";
error_log "{self.directory / "nginx-error.log"}";
events {{ worker_connections 1024; }}
http {{
    include /etc/nginx/mime.types;
    client_body_temp_path "{self.directory / "nginx-temp/client"}";
    proxy_temp_path "{self.directory / "nginx-temp/proxy"}";
    fastcgi_temp_path "{self.directory / "nginx-temp/fastcgi"}";
    uwsgi_temp_path "{self.directory / "nginx-temp/uwsgi"}";
    scgi_temp_path "{self.directory / "nginx-temp/scgi"}";
{include_text}
}}
''',
        )
        self.runner.run(
            [
                "nginx",
                "-t",
                "-p",
                str(self.directory) + "/",
                "-c",
                str(self.directory / "nginx.conf"),
            ],
            label="Native Nginx validation",
        )

    def run(self) -> None:
        """Install only application packages and processes; reuse existing database gates."""
        with operation_lock(self.directory):
            self._run_unlocked()

    def control(self, operation: str) -> None:
        """Manage application lifecycle without overlapping a deployment or database lifecycle."""
        names = list(self.commands())
        if operation == "status":
            for name, state in self.services.status(names).items():
                self.console.log(f"{name}: {state}")
        elif operation == "logs":
            self.services.logs(names)
        elif operation in {"start", "stop", "restart"}:
            with operation_lock(self.directory):
                if operation in {"stop", "restart"}:
                    self.services.stop(names)
                if operation in {"start", "restart"}:
                    self._run_unlocked()
        else:
            raise ValueError("Unsupported native lifecycle operation")

    def _run_unlocked(self) -> None:
        """Execute validated installation steps while the caller owns the operation lock."""
        self.options.validate()
        self.profile.validate()
        missing = [
            name
            for name in ("uv", "npm", "nginx", "systemctl", "systemd-run", "curl")
            if not shutil.which(name)
        ]
        if missing:
            raise ValueError("Install native prerequisites first: " + ", ".join(missing))
        selected = set(self.options.steps)
        if selected & {"directories", "build", "bootstrap", "indexes", "start"}:
            self.services.assert_stopped(list(self.commands()))
        if "start" in selected:
            self._check_ports()
        if "directories" in selected:
            self._prepare()
        if "build" in selected and not self.options.skip_build:
            self._build()
        if selected & {"validate", "bootstrap", "indexes", "start"}:
            self._check("redis")
        identity_uri = (
            private_uri(self.options.identity_maintenance_uri_file)
            if self.options.identity_maintenance_uri_file
            else ""
        )
        knowledge_uri = (
            private_uri(self.options.knowledgebase_maintenance_uri_file)
            if self.options.knowledgebase_maintenance_uri_file
            else ""
        )
        self._apply(self.target, identity_uri=identity_uri, knowledge_uri=knowledge_uri)
        self.console.complete()

    def _check_ports(self) -> None:
        """Fail before bootstrap if another installation already owns a local listener."""
        for name, port in self.ports.items():
            kind = socket.SOCK_DGRAM if name == "monitor" else socket.SOCK_STREAM
            try:
                with socket.socket(socket.AF_INET, kind) as listener:
                    listener.bind(("127.0.0.1", port))
            except OSError:
                raise ValueError(
                    f"Native {name} port {port} is unavailable; select a different port"
                ) from None

    def _start(self) -> None:
        self._web_configuration()
        self.environment["COYOTE4_API_INTERNAL_URL"] = f"http://127.0.0.1:{self.ports['api']}"
        self.environment["CHOKIDAR_USEPOLLING"] = "true"
        write_environment(self.directory / "runtime.json", self.environment)
        public_file = self.directory / "public-runtime.json"
        write_environment(public_file, self.public_environment())
        started = []
        try:
            for name, command in self.commands().items():
                self.services.start(
                    name,
                    command,
                    environment_file=public_file if name in {"frontend", "proxy"} else None,
                )
                started.append(name)
                if name == "api":
                    self.runner.run(
                        [
                            "curl",
                            "--fail",
                            "--silent",
                            "--retry",
                            "15",
                            "--retry-connrefused",
                            "--retry-delay",
                            "2",
                            "--max-time",
                            "5",
                            f"http://127.0.0.1:{self.ports['api']}/api/v1/health",
                        ],
                        label="Native API readiness",
                    )
            failed = [
                name for name, state in self.services.status(started).items() if state != "active"
            ]
            if failed:
                raise RuntimeError("Native services did not remain active: " + ", ".join(failed))
        except BaseException:
            self.services.stop(started)
            raise
