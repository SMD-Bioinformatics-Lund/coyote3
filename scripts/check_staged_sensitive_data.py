#!/usr/bin/env python3
"""Block high-confidence secrets and clinical identifiers from staged content.

The checker is intentionally conservative about what it classifies as sensitive:
it blocks credentials, private key material, local paths, known clinical sample
formats, Swedish personal identity numbers, and non-synthetic sample metadata in
test data. It does not infer whether genomic coordinates are derived from a
patient; fixture provenance remains a reviewer responsibility.
"""

from __future__ import annotations

import argparse
import gzip
import re
import subprocess
import sys
from pathlib import Path, PurePosixPath

BLOCKED_PRIVATE_FILENAMES = {
    ".env",
    ".env.dev",
    ".env.local",
    ".env.production",
    ".env.stage",
    ".env.test",
    ".coyote3_dev_env",
    ".coyote3_env",
    ".coyote3_stage_env",
    ".coyote3_test_env",
    "id_rsa",
    "id_ed25519",
    "credentials.json",
}
BLOCKED_PRIVATE_SUFFIXES = (".pem", ".key", ".p12", ".pfx")
BINARY_SUFFIXES = (
    ".gif",
    ".ico",
    ".jpeg",
    ".jpg",
    ".pdf",
    ".png",
    ".svg",
    ".webp",
    ".woff",
    ".woff2",
)
SAFE_VALUE_MARKERS = ("CHANGE_ME", "EXAMPLE", "YOUR_", "TEST", "DEMO", "SEED", "DUMMY", "REPLACE")
SYNTHETIC_VALUE_MARKERS = ("seed", "demo", "example", "dummy", "synthetic", "fixture", "test")

CONTENT_RULES = (
    ("private key material", re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----")),
    ("AWS access key", re.compile(r"\bAKIA[0-9A-Z]{16}\b")),
    (
        "GitHub token",
        re.compile(r"\b(?:gh[pousr]_[A-Za-z0-9_]{20,}|github_pat_[A-Za-z0-9_]{20,})\b"),
    ),
    ("Slack token", re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{20,}\b")),
    ("OpenAI-style API key", re.compile(r"\bsk-[A-Za-z0-9]{20,}\b")),
    (
        "clinical sample identifier",
        re.compile(r"\b(?:26MD|26PH)[0-9]{5,}(?:[A-Za-z]|[-_][A-Za-z0-9]+)?\b", re.IGNORECASE),
    ),
    ("Swedish personal identity number", re.compile(r"\b(?:18|19|20)?[0-9]{6}[-+]?[0-9]{4}\b")),
    (
        "local workstation path",
        re.compile(r"(?:/home/[A-Za-z0-9._-]+/|/Users/[A-Za-z0-9._-]+/|[A-Za-z]:\\\\Users\\)"),
    ),
)
ENV_SECRET_ASSIGNMENT = re.compile(
    r"^(?:[A-Z0-9_]*_)?(?:PASSWORD|SECRET|TOKEN|API_KEY|PRIVATE_KEY)=(.*)$",
    re.MULTILINE,
)
SAMPLE_FIELD = re.compile(
    r"^\s*(?:name|sample_id|case_id|control_id|clarity_case_id|clarity_control_id)\s*:\s*['\"]?([^'\"\s#]+)",
    re.MULTILINE | re.IGNORECASE,
)


def _git(*args: str) -> bytes:
    return subprocess.check_output(("git", *args))


def _staged_paths() -> list[str]:
    raw = _git("diff", "--cached", "--name-only", "--diff-filter=ACMR", "-z")
    return [item.decode("utf-8") for item in raw.split(b"\0") if item]


def _read_staged(path: str) -> bytes:
    return _git("show", f":{path}")


def _read_worktree(path: str) -> bytes:
    return Path(path).read_bytes()


def _decode(path: str, content: bytes) -> str:
    if path.endswith(".gz"):
        content = gzip.decompress(content)
    return content.decode("utf-8", errors="replace")


def _is_private_filename(path: str) -> bool:
    name = PurePosixPath(path).name
    return name in BLOCKED_PRIVATE_FILENAMES or name.endswith(BLOCKED_PRIVATE_SUFFIXES)


def _is_safe_secret_value(raw_value: str) -> bool:
    value = raw_value.strip().strip("'\"")
    return (
        not value
        or value.startswith("${")
        or any(marker in value.upper() for marker in SAFE_VALUE_MARKERS)
    )


def _is_synthetic(value: str) -> bool:
    candidate = value.lower()
    return any(marker in candidate for marker in SYNTHETIC_VALUE_MARKERS)


def _find_violations(path: str, content: bytes) -> list[str]:
    violations: list[str] = []
    if _is_private_filename(path):
        return ["private environment, credential, or key file"]
    if path.lower().endswith(BINARY_SUFFIXES):
        return violations

    try:
        text = _decode(path, content)
    except (OSError, UnicodeError) as error:
        return [f"unreadable compressed or text content ({error})"]

    for label, pattern in CONTENT_RULES:
        if pattern.search(text):
            violations.append(label)

    if PurePosixPath(path).name.endswith(".env") or "/env/" in f"/{path}":
        for match in ENV_SECRET_ASSIGNMENT.finditer(text):
            if not _is_safe_secret_value(match.group(1)):
                violations.append(
                    f"non-placeholder secret assignment: {match.group(0).split('=', 1)[0]}"
                )

    fixture_suffixes = (".json", ".ndjson", ".toml", ".yaml", ".yml", ".gz")
    if path.startswith("tests/") and path.lower().endswith(fixture_suffixes):
        for match in SAMPLE_FIELD.finditer(text):
            if not _is_synthetic(match.group(1)):
                violations.append(f"non-synthetic sample metadata: {match.group(0).strip()}")

    return violations


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--all-files",
        action="store_true",
        help="scan tracked worktree files instead of staged content",
    )
    args = parser.parse_args()

    paths = (
        _git("ls-files", "-z").decode("utf-8").split("\0") if args.all_files else _staged_paths()
    )
    findings: list[tuple[str, list[str]]] = []
    for path in filter(None, paths):
        content = _read_worktree(path) if args.all_files else _read_staged(path)
        violations = _find_violations(path, content)
        if violations:
            findings.append((path, violations))

    if not findings:
        print("Sensitive-data check passed.")
        return 0

    print(
        "Sensitive-data check failed. Remove or replace the following staged content:",
        file=sys.stderr,
    )
    for path, violations in findings:
        print(f"- {path}: {', '.join(sorted(set(violations)))}", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
