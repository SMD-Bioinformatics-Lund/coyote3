# SPDX-FileCopyrightText: 2026 Ram Nanduri
# SPDX-License-Identifier: GPL-3.0-only

"""One command line for reviewed installation profiles and deployment operations."""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

from .compose import Compose
from .config import (
    ENVIRONMENTS,
    STEPS,
    Profile,
    environment_name,
    read_environment,
    validate_secrets,
)
from .process import Console, Runner
from .workflow import Installer, Options


def _profile_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--profile", action="append", help="Enable a Compose service group; may be repeated"
    )
    parser.add_argument("--env-file", type=Path, required=True, help="Reviewed environment file")
    parser.add_argument(
        "--environment",
        type=environment_name,
        choices=tuple(ENVIRONMENTS.values()),
        help=(
            f"Deployment environment; also accepts full names: {', '.join(ENVIRONMENTS)}. "
            "Must match ENV_NAME after normalization; otherwise inferred from the file"
        ),
    )
    parser.add_argument(
        "--project",
        "--project-name",
        "-p",
        help="Stable Compose project name (default: coyote4-ENV)",
    )
    parser.add_argument(
        "--compose-file",
        "--file",
        "-f",
        type=Path,
        action="append",
        dest="files",
        help="Complete ordered file selection instead of the profile defaults; repeat for overlays",
    )
    parser.add_argument(
        "--overlay",
        type=Path,
        action="append",
        help="Append a Compose overlay to the selected profile",
    )
    parser.add_argument(
        "--legacy", action="store_true", help="Use the maintained older-host Compose files"
    )


def _profile(args: argparse.Namespace) -> Profile:
    return Profile.load(
        args.env_file,
        environment=args.environment,
        project=args.project,
        files=args.files,
        overlays=args.overlay,
        legacy=args.legacy,
        service_profiles=args.profile,
    )


def _installation_arguments(parser: argparse.ArgumentParser) -> None:
    _profile_arguments(parser)
    parser.add_argument(
        "--steps",
        default=",".join(STEPS),
        help="Comma-separated stages, run in canonical order: " + ",".join(STEPS),
    )
    for name, help_text in {
        "skip-build": "Use existing images",
        "skip-users": "Skip accounts; requires skipping application and knowledgebase data",
        "skip-application": "Skip application factory records on a fresh target",
        "skip-knowledgebase": "Skip bundled knowledgebase records on a fresh target",
        "with-knowledgebase-indexes": "Explicitly include knowledgebase indexes",
    }.items():
        parser.add_argument("--" + name, action="store_true", help=help_text)
    for name in ("identity-maintenance-uri-file", "knowledgebase-maintenance-uri-file"):
        parser.add_argument(
            "--" + name,
            type=Path,
            help="Owner-only credential file, scoped to the selected maintenance operation",
        )
    system_admin = parser.add_argument_group(
        "Initial system administrator (sys_admin)",
        "Manages accounts, access and system operations; the clinical admin role is separate.",
    )
    system_admin.add_argument(
        "--system-admin-username",
        metavar="USERNAME",
        help="Fixed login: coyote4.sysadmin; used only on a fresh target",
    )
    system_admin.add_argument(
        "--system-admin-email",
        metavar="EMAIL",
        help="Contact email for the initial system administrator",
    )
    superuser = parser.add_argument_group(
        "Initial emergency superuser (superuser)",
        "Privileged account for initial setup and controlled recovery.",
    )
    superuser.add_argument(
        "--superuser-username",
        metavar="USERNAME",
        help="Fixed login: coyote4.superuser; used only on a fresh target",
    )
    superuser.add_argument(
        "--superuser-email",
        metavar="EMAIL",
        help="Contact email for the initial emergency superuser",
    )


def _compose(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(
        prog="install.sh compose",
        description="Versioned Compose operations. Place installer options before the Compose command.",
    )
    _profile_arguments(parser)
    parser.add_argument(
        "--prepare-directories",
        action="store_true",
        help="Explicitly prepare host storage before the command",
    )
    # REMAINDER prevents flags or words inside `run`/`exec` from becoming installer actions.
    parser.add_argument("command", nargs=argparse.REMAINDER)
    args = parser.parse_args(argv)
    if args.command and args.command[0] == "--":
        args.command = args.command[1:]
    if not args.command:
        parser.error("a Compose command is required")
    profile = _profile(args)
    runner = Runner(profile.process_env)
    compose = Compose(profile, runner)
    if args.prepare_directories:
        from .storage import prepare

        prepare(compose.config())
    compose.run(args.command)
    return 0


def _check(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(
        prog="install.sh check",
        description="Check local settings without database or service connections.",
    )
    _profile_arguments(parser)
    parser.add_argument(
        "--resolved",
        action="store_true",
        help="Render Compose locally and validate center files and storage; requires host server packages",
    )
    parser.add_argument(
        "--prepare-directories",
        action="store_true",
        help="Explicitly create application storage; requires --resolved",
    )
    args = parser.parse_args(argv)
    validate_secrets(read_environment(args.env_file))
    if args.prepare_directories and not args.resolved:
        parser.error("--prepare-directories requires --resolved")
    if args.resolved:
        from .preflight import validate
        from .storage import prepare

        profile = _profile(args)
        compose = Compose(profile, Runner(profile.process_env))
        config = compose.config()
        compose.validate()
        if args.prepare_directories:
            prepare(config)
        validate(config)
    Console().log("Environment secrets passed local validation", "DONE")
    return 0


def main(argv: list[str] | None = None) -> int:
    """Dispatch one explicit operation; help and local plans do not load application packages.

    Args:
        argv: Arguments, or the current process arguments when omitted.

    Returns:
        Zero on success, one on an operational failure, or 130 after interruption.
    """
    argv = list(sys.argv[1:] if argv is None else argv)
    console = Console()
    try:
        if argv and argv[0] == "compose":
            return _compose(argv[1:])
        if argv and argv[0] == "check":
            return _check(argv[1:])
        if argv and argv[0] in {"center", "data", "demo"}:
            if argv[0] == "center":
                from .center import main as command
            elif argv[0] == "data":
                from .data import main as command
            else:
                from .demo import main as command
            return command(argv[1:]) or 0
        parser = argparse.ArgumentParser(
            prog="install.sh",
            description="Install and manage Coyote4. Regular deployments preserve existing databases; demo uses isolated targets.",
        )
        commands = parser.add_subparsers(dest="operation", required=True)
        for name, description in {
            "deploy": "Build, validate, bootstrap fresh targets and start services",
            "plan": "Show the selected deployment without writes or service connections",
        }.items():
            _installation_arguments(
                commands.add_parser(name, help=description, description=description)
            )
        for name, description in {
            "compose": "Run versioned Compose lifecycle commands",
            "check": "Check environment secrets locally",
            "center": "Stage a reviewed center configuration release",
            "data": "Install or repair selected factory data through an authenticated API",
            "demo": "Prepare and run an isolated Docker or native demonstration",
        }.items():
            commands.add_parser(name, help=description)
        args = parser.parse_args(argv)
        options = {
            name: getattr(args, name) for name in Options.__dataclass_fields__ if name != "steps"
        }
        installer = Installer(
            _profile(args), Options(steps=tuple(args.steps.split(",")), **options), console=console
        )
        if args.operation == "plan":
            installer.plan()
        else:
            installer.run()
        return 0
    except KeyboardInterrupt:
        console.log("Interrupted; completed stages are preserved", "WARN")
        return 130
    except ImportError as error:
        console.log(
            f"Required installation dependency is unavailable: {error.name}. Install the documented workspace extras for this operation.",
            "ERROR",
        )
        return 1
    except subprocess.CalledProcessError as error:
        console.log(
            f"Installation subprocess failed (exit {error.returncode}); selected operation stopped",
            "ERROR",
        )
        return 1
    except (OSError, ValueError, RuntimeError) as error:
        console.log(str(error), "ERROR")
        return 1
