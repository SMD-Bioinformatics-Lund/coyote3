#!/usr/bin/env python3
"""Upload an analysis-server manifest and apply its terminal API acknowledgement.

Requires Python 3.10+ and curl, plus SSH/SCP for remote inputs. No application
imports or database access are used.
"""

from __future__ import annotations

import argparse
import fcntl
import hashlib
import json
import os
import re
import shlex
import subprocess
import sys
import tempfile
from pathlib import Path
from types import SimpleNamespace
from urllib.parse import urlsplit


def fingerprint(path: Path) -> str:
    """Hash the manifest so an acknowledgement cannot rename subsequently edited input."""
    return hashlib.sha256(path.read_bytes()).hexdigest()


def form_file(field: str, path: Path, content_type: str) -> str:
    """Quote a local filename for curl's multipart form syntax."""
    escaped = str(path).replace("\\", "\\\\").replace('"', '\\"')
    return f'{field}=@"{escaped}";type={content_type}'


def upload(args: argparse.Namespace, manifest: Path, token: str) -> dict:
    """Stream multipart files to the API and require a terminal acknowledgement.

    Raises:
        ValueError: Transport, HTTP, or response validation fails; outcome is unconfirmed.
    """
    command = [
        "curl",
        "--silent",
        "--show-error",
        "--config",
        "-",
        "--connect-timeout",
        "15",
        "--max-time",
        str(args.timeout),
        "--write-out",
        "\n%{http_code}",
        "--form",
        form_file("yaml_file", manifest, "text/yaml"),
        "--form",
        "acknowledge=true",
        "--form",
        f"update_existing={str(args.update_existing).lower()}",
        "--form",
        f"increment={str(args.increment).lower()}",
    ]
    if args.archive:
        archive = Path(args.archive).expanduser().resolve(strict=True)
        if not archive.is_file():
            raise ValueError("The archive must be a regular ZIP file")
        command.extend(["--form", form_file("data_archive", archive, "application/zip")])
    if args.ca_bundle:
        command.extend(["--cacert", args.ca_bundle])
    command.append(args.base_url + "/api/v1/internal/ingest/sample-bundle/upload")
    # Keep credentials out of process arguments and shell history.
    header = (
        f"X-Coyote-Internal-Token: {token}"
        if args.auth == "internal"
        else f"Authorization: Bearer {token}"
    )
    if args.auth == "ingest":
        header = f"X-Coyote-Ingest-Token: {token}"
    config = f'header = "{header}"\n'
    result = subprocess.run(command, input=config, text=True, capture_output=True, check=False)
    if result.returncode:
        raise ValueError(
            f"Upload transport failed (curl exit {result.returncode}); ingest outcome is unconfirmed"
        )
    body, _, code = result.stdout.rpartition("\n")
    if not code.isdigit() or not 200 <= int(code) < 300:
        raise ValueError(
            f"API returned HTTP {code or 'unknown'}; no terminal ingest acknowledgement"
        )
    try:
        acknowledgement = json.loads(body)
    except ValueError as exc:
        raise ValueError("API response is not JSON; ingest outcome is unconfirmed") from exc
    if (
        not isinstance(acknowledgement, dict)
        or acknowledgement.get("status") not in {"ok", "failed"}
        or not isinstance(acknowledgement.get("message"), str)
    ):
        raise ValueError("API response is not a terminal ingest acknowledgement")
    if acknowledgement["status"] == "ok" and not acknowledgement.get("sample_id"):
        raise ValueError("Successful acknowledgement is missing sample_id")
    return acknowledgement


def save_receipt(path: Path, receipt: dict) -> None:
    """Atomically persist a private receipt before moving the manifest."""
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", dir=path.parent, prefix=path.name, delete=False
        ) as stream:
            temporary = Path(stream.name)
            json.dump(receipt, stream, indent=2)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def remote_connection(args: argparse.Namespace, program: str) -> list[str]:
    """Build noninteractive SSH/SCP options without disabling host-key verification."""
    command = [program, "-o", "BatchMode=yes", "-o", "ConnectTimeout=15"]
    if args.identity_file:
        command.extend(["-i", args.identity_file])
    command.extend(["-P" if program == "scp" else "-p", str(args.ssh_port)])
    return command


def remote_command(args: argparse.Namespace, script: str, *parameters: str) -> None:
    """Run a quoted shell operation on the analysis server; propagate any failure."""
    command = remote_connection(args, "ssh") + [
        args.remote_host,
        "sh -s -- " + " ".join(shlex.quote(value) for value in parameters),
    ]
    result = subprocess.run(command, input=script, text=True, capture_output=True, check=False)
    if result.returncode:
        raise ValueError(
            f"Remote operation failed: {result.stderr.strip() or 'SSH connection failed'}"
        )


def fetch_remote(args: argparse.Namespace, source: str, destination: Path) -> None:
    """Fetch one literal absolute remote path with SCP, without wildcard expansion."""
    if not re.fullmatch(r"/[A-Za-z0-9_./-]+", source):
        raise ValueError(
            "Remote paths must be absolute and contain only letters, numbers, /, _, ., or -"
        )
    command = remote_connection(args, "scp") + [
        "-q",
        f"{args.remote_host}:{source}",
        str(destination),
    ]
    result = subprocess.run(command, text=True, capture_output=True, check=False)
    if result.returncode:
        raise ValueError(f"SCP failed: {result.stderr.strip() or 'file transfer failed'}")


def finalize_remote(args: argparse.Namespace, receipt: dict) -> int:
    """Apply a saved result remotely only while the original YAML hash still matches."""
    if (
        receipt.get("base_url") != args.base_url
        or receipt.get("remote_host") != args.remote_host
        or receipt.get("remote_path") != args.yaml
    ):
        raise ValueError("Saved acknowledgement belongs to another remote input or API")
    acknowledgement = receipt["acknowledgement"]
    if acknowledgement.get("status") not in {"ok", "failed"}:
        raise ValueError("Saved acknowledgement has no terminal status")
    suffix = ".done" if acknowledgement["status"] == "ok" else ".failed"
    remote_command(
        args,
        """set -eu
source=$1
destination=$2
expected=$3
fail() { echo "$1" >&2; exit 1; }
check_hash() {
    actual=$(sha256sum -- "$1")
    actual=${actual%% *}
    [ "$actual" = "$expected" ] || fail "Remote YAML changed; acknowledgement retained, file not renamed"
}
if [ ! -e "$source" ] && [ ! -L "$source" ]; then
    [ -f "$destination" ] && [ ! -L "$destination" ] || fail "Neither original YAML nor acknowledged destination exists"
    check_hash "$destination"
    exit 0
fi
[ -f "$source" ] && [ ! -L "$source" ] || fail "Remote YAML is not a regular file"
check_hash "$source"
if [ -e "$destination" ] || [ -L "$destination" ]; then
    [ "$source" -ef "$destination" ] || fail "Acknowledgement destination exists; it will not be overwritten"
else
    ln -- "$source" "$destination"
fi
rm -- "$source"
""",
        args.yaml,
        args.yaml + suffix,
        receipt["sha256"],
    )
    print(f"{acknowledgement['status']}: {acknowledgement['message']}")
    print(f"Remote manifest: {args.remote_host}:{args.yaml + suffix}")
    return 0 if suffix == ".done" else 1


def submit_remote(args: argparse.Namespace) -> int:
    """Fetch inputs on the deployment server and finalize the analysis-server YAML.

    A saved terminal receipt is reused after SSH failures without another upload.
    The local state lock serializes submissions from this deployment server.
    """
    if not re.fullmatch(r"[A-Za-z0-9_][A-Za-z0-9_.@-]*", args.remote_host):
        raise ValueError("Use an SSH config alias or user@hostname for --remote-host")
    if not re.fullmatch(r"/[A-Za-z0-9_./-]+\.ya?ml", args.yaml):
        raise ValueError(
            "Remote YAML must be an absolute literal .yaml or .yml path without shell metacharacters"
        )
    state = Path(args.state_dir).expanduser().absolute()
    state.mkdir(parents=True, exist_ok=True, mode=0o700)
    key = hashlib.sha256(f"{args.remote_host}:{args.yaml}".encode()).hexdigest()
    receipt_path = state / (key + ".ack.json")
    with (state / (key + ".lock")).open("a") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise ValueError("Another process is submitting this remote manifest") from exc
        if receipt_path.exists():
            result = finalize_remote(args, json.loads(receipt_path.read_text()))
            print(f"Acknowledgement: {receipt_path}")
            return result
        remote_command(
            args,
            """set -eu
[ -f "$1" ] && [ ! -L "$1" ] || { echo "Remote YAML is not a regular file" >&2; exit 1; }
for destination in "$1.done" "$1.failed"; do
    if [ -e "$destination" ] || [ -L "$destination" ]; then
        echo "Remote completion marker already exists; refusing to submit" >&2
        exit 1
    fi
done
""",
            args.yaml,
        )
        token_variable = {
            "internal": "INTERNAL_API_TOKEN",
            "bearer": "API_BEARER_TOKEN",
            "ingest": "COYOTE3_INGEST_TOKEN",
        }[args.auth]
        token = os.environ.get(token_variable, "").strip()
        if not token or any(char in token for char in '\r\n"\\'):
            raise ValueError(f"Set {token_variable} to a valid {args.auth} token")
        with tempfile.TemporaryDirectory(prefix="coyote3-upload-") as staging:
            manifest = Path(staging) / Path(args.yaml).name
            fetch_remote(args, args.yaml, manifest)
            local_args = SimpleNamespace(**vars(args))
            if args.archive:
                archive = Path(staging) / "inputs.zip"
                fetch_remote(args, args.archive, archive)
                local_args.archive = str(archive)
            acknowledgement = upload(local_args, manifest, token)
            receipt = {
                "base_url": args.base_url,
                "remote_host": args.remote_host,
                "remote_path": args.yaml,
                "sha256": fingerprint(manifest),
                "acknowledgement": acknowledgement,
            }
            save_receipt(receipt_path, receipt)
        print(f"Acknowledgement saved: {receipt_path}", flush=True)
        return finalize_remote(args, receipt)


def submit(args: argparse.Namespace) -> int:
    """Submit once, or finish a previously acknowledged local file transition.

    Returns:
        Zero for acknowledged success or one for acknowledged ingest failure.

    Raises:
        ValueError: Input, saved receipt, or acknowledgement is invalid.
        OSError: A local file operation fails; existing destination files are retained.
    """
    manifest = Path(args.yaml).expanduser().absolute()
    if manifest.is_symlink() or manifest.suffix.lower() not in {".yaml", ".yml"}:
        raise ValueError("Supply a regular .yaml or .yml manifest, not a symbolic link")
    receipt_path = manifest.with_name(manifest.name + ".ack.json")
    with manifest.with_name(manifest.name + ".submit.lock").open("a") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise ValueError("Another process is submitting this manifest") from exc
        if not manifest.is_file():
            raise ValueError("Manifest does not exist or is not a regular file")
        digest = fingerprint(manifest)
        for suffix in (".done", ".failed"):
            if manifest.with_name(manifest.name + suffix).exists():
                raise ValueError(
                    f"Destination {manifest.name + suffix} already exists; it will not be overwritten"
                )
        if receipt_path.exists():
            receipt = json.loads(receipt_path.read_text())
            if receipt.get("sha256") != digest or receipt.get("base_url") != args.base_url:
                raise ValueError(
                    "Saved acknowledgement belongs to different input or another API; review it before resubmitting"
                )
            acknowledgement = receipt["acknowledgement"]
            if acknowledgement.get("status") not in {"ok", "failed"}:
                raise ValueError("Saved acknowledgement has no terminal status")
        else:
            token_variable = {
                "internal": "INTERNAL_API_TOKEN",
                "bearer": "API_BEARER_TOKEN",
                "ingest": "COYOTE3_INGEST_TOKEN",
            }[args.auth]
            token = os.environ.get(token_variable, "").strip()
            if not token or any(char in token for char in '\r\n"\\'):
                raise ValueError(f"Set {token_variable} to a valid {args.auth} token")
            acknowledgement = upload(args, manifest, token)
            save_receipt(
                receipt_path,
                {"sha256": digest, "base_url": args.base_url, "acknowledgement": acknowledgement},
            )
        if fingerprint(manifest) != digest:
            raise ValueError(
                "Manifest changed during submission; acknowledgement saved but file left unchanged"
            )
        suffix = ".done" if acknowledgement["status"] == "ok" else ".failed"
        destination = manifest.with_name(manifest.name + suffix)
        # Link/unlink preserves the file and refuses to overwrite a racing destination.
        os.link(manifest, destination)
        manifest.unlink()
        print(f"{acknowledgement['status']}: {acknowledgement['message']}")
        print(f"Manifest: {destination}\nAcknowledgement: {receipt_path}")
        return 0 if suffix == ".done" else 1


def main(argv: list[str] | None = None) -> int:
    """Parse the standalone client arguments and report unconfirmed outcomes as exit 2."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("yaml", help="Manifest path, on --remote-host when supplied")
    parser.add_argument(
        "--remote-host",
        help="Analysis-server SSH alias or user@hostname; fetch via SCP and acknowledge via SSH",
    )
    parser.add_argument("--ssh-port", type=int, default=22)
    parser.add_argument(
        "--identity-file", help="SSH private key path, if not using the SSH agent/config"
    )
    parser.add_argument(
        "--state-dir",
        default=str(
            Path(os.environ.get("XDG_STATE_HOME", str(Path.home() / ".local/state")))
            / "coyote3-ingest"
        ),
        help="Durable local receipts for remote inputs",
    )
    parser.add_argument(
        "--auth",
        choices=("internal", "bearer", "ingest"),
        default="internal",
        help="Use INTERNAL_API_TOKEN (default), COYOTE3_INGEST_TOKEN (ingest), or API_BEARER_TOKEN (bearer)",
    )
    parser.add_argument(
        "--base-url",
        default=os.environ.get("COYOTE3_BASE_URL"),
        help="Application URL including its prefix, e.g. https://host/coyote3_dev",
    )
    parser.add_argument(
        "--archive", help="Optional ZIP; remote path when --remote-host is supplied"
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=1800,
        help="Upload and synchronous ingest timeout in seconds (default: 1800)",
    )
    parser.add_argument(
        "--ca-bundle", help="Trusted CA bundle for the application HTTPS certificate"
    )
    parser.add_argument("--update-existing", action="store_true")
    parser.add_argument("--increment", action="store_true")
    args = parser.parse_args(argv)
    args.base_url = str(args.base_url or "").rstrip("/")
    url = urlsplit(args.base_url)
    if (
        url.scheme not in {"http", "https"}
        or not url.hostname
        or url.username
        or url.password
        or url.query
        or url.fragment
    ):
        parser.error(
            "--base-url must be an HTTP(S) application URL without credentials, query, or fragment"
        )
    if args.timeout <= 0:
        parser.error("--timeout must be positive")
    if not 1 <= args.ssh_port <= 65535:
        parser.error("--ssh-port must be between 1 and 65535")
    try:
        return submit_remote(args) if args.remote_host else submit(args)
    except (OSError, ValueError, KeyError, TypeError) as exc:
        print(f"Submission not finalized: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
