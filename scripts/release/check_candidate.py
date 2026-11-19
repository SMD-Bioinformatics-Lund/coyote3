#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Ram Nanduri
# SPDX-License-Identifier: GPL-3.0-only

"""Retain release-candidate test evidence and reject incomplete or mismatched runs."""

import argparse
import hashlib
import json
import re
import subprocess
import sys
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from scripts.release.check_release import release_identity, wheel_record

ROOT = Path(__file__).resolve().parents[2]


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def junit_result(path: Path) -> dict[str, Any]:
    """Require actual executed cases, with no failures, errors, skips or expected failures."""
    root = ET.parse(path).getroot()
    cases = list(root.iter("testcase"))
    if not cases or any(list(root.iter(tag)) for tag in ("failure", "error", "skipped")):
        raise ValueError("Mandatory backend tests must all execute and pass")
    declared = sum(int(suite.get("tests", "0")) for suite in root.iter("testsuite"))
    if any(
        int(suite.get(outcome, "0")) != 0
        for suite in root.iter("testsuite")
        for outcome in ("failures", "errors", "skipped")
    ):
        raise ValueError("Mandatory backend tests must all execute and pass")
    if declared != len(cases):
        raise ValueError("Incomplete backend test report")
    return {"passed": len(cases), "report_sha256": digest(path)}


def browser_result(directory: Path, commit: str) -> dict[str, Any]:
    """Accept only a complete, cleaned-up disposable run on this candidate."""
    run = json.loads((directory / "run.json").read_text())
    result = json.loads((directory / "browser-results.json").read_text())
    stats = result.get("stats", {})
    if (
        run.get("source_commit") != commit
        or run.get("source_dirty") is not False
        or run.get("synthetic_only") is not True
        or run.get("browser_exit_code") != 0
        or set(run.get("remaining_resources", {})) != {"container", "network", "volume"}
        or any(run["remaining_resources"].values())
        or not run.get("images")
        or stats.get("expected", 0) <= 0
        or any(stats.get(key, -1) != 0 for key in ("unexpected", "flaky", "skipped"))
        or result.get("errors")
    ):
        raise ValueError("Browser acceptance is incomplete, failed, or belongs to another commit")
    return {
        "passed": stats["expected"],
        "images": run["images"],
        "report_sha256": digest(directory / "browser-results.json"),
        "run_sha256": digest(directory / "run.json"),
    }


def backend_result(report: Path, wheels: Path) -> dict[str, Any]:
    tests = junit_result(report)
    identity = release_identity(ROOT)
    versions = {
        "coyote-core": identity["sdk_version"],
        "coyote-server": identity["server_version"],
        "coyote-relay": identity["relay_version"],
        "coyote-atlas": identity["atlas_version"],
        "coyote-demo": identity["demo_version"],
    }
    artifacts = {}
    for distribution, version in versions.items():
        matching = list(wheels.glob(distribution.replace("-", "_") + "-*.whl"))
        if len(matching) != 1:
            raise ValueError(f"Expected one tested wheel for {distribution}")
        artifacts[distribution] = wheel_record(matching[0], version, distribution)
    if len(list(wheels.glob("*.whl"))) != len(versions):
        raise ValueError("Unexpected release wheel set")
    return {**tests, "release": identity, "wheels": artifacts}


def gate(records: list[Path], commit: str) -> dict[str, Any]:
    evidence = [json.loads(path.read_text()) for path in records]
    if (
        len(evidence) != 2
        or {row.get("kind") for row in evidence} != {"backend", "browser"}
        or any(
            row.get("source_commit") != commit or row.get("status") != "passed" for row in evidence
        )
        or any(row.get("result", {}).get("passed", 0) <= 0 for row in evidence)
    ):
        raise ValueError("Release requires successful backend and browser evidence for this commit")
    return {
        row["kind"]: {"evidence_sha256": digest(path), **row["result"]}
        for path, row in zip(records, evidence, strict=True)
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("kind", choices=("backend", "browser", "gate"))
    parser.add_argument("--commit", required=True, help="Exact candidate Git SHA")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--junit", type=Path)
    parser.add_argument("--wheels", type=Path)
    parser.add_argument("--browser-directory", type=Path)
    parser.add_argument("--evidence", type=Path, nargs="+")
    args = parser.parse_args()
    if not re.fullmatch(r"[0-9a-f]{40}", args.commit):
        parser.error("Candidate must be a full Git commit SHA")
    try:
        head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
        if head != args.commit:
            raise ValueError("Checked-out commit differs from the candidate")
        subprocess.run(
            ["git", "diff", "--exit-code", "HEAD", "--"],
            cwd=ROOT,
            check=True,
            stdout=subprocess.DEVNULL,
        )
        if args.kind == "backend" and args.junit and args.wheels:
            result = backend_result(args.junit, args.wheels)
        elif args.kind == "browser" and args.browser_directory:
            result = browser_result(args.browser_directory, args.commit)
        elif args.kind == "gate" and args.evidence:
            result = gate(args.evidence, args.commit)
        else:
            parser.error(
                "Supply the test report and artifacts required for the selected evidence kind"
            )
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(
            json.dumps(
                {
                    "kind": args.kind,
                    "status": "passed",
                    "source_commit": args.commit,
                    "recorded_at": datetime.now(timezone.utc).isoformat(),
                    "python": sys.version.split()[0],
                    "result": result,
                },
                indent=2,
                sort_keys=True,
            )
            + "\n"
        )
    except (OSError, ValueError, ET.ParseError, subprocess.CalledProcessError) as exc:
        parser.exit(1, f"Candidate evidence rejected: {exc}\n")


if __name__ == "__main__":
    main()
