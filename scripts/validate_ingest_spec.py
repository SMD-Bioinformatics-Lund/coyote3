#!/usr/bin/env python3
"""Validate a Coyote3 ingestion YAML spec before API submission."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import yaml
from pydantic import ValidationError

# Ensure repo root is importable when running as `python scripts/...`.
REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

REQUIRED_ONE_OF = (("vcf_files", "fusion_files"),)

FILE_FIELDS = (
    "vcf_files",
    "cnv",
    "cov",
    "transloc",
    "biomarkers",
    "fusion_files",
    "expression_path",
    "classification_path",
    "qc",
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate Coyote3 ingest spec YAML")
    parser.add_argument("--yaml", required=True, help="Path to YAML spec file")
    parser.add_argument(
        "--check-files",
        action="store_true",
        help="Verify referenced input file paths exist",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print normalized payload as JSON",
    )
    return parser.parse_args()


def main() -> int:
    from api.contracts.internal import InternalSampleIngestSpec

    args = parse_args()
    spec_path = Path(args.yaml)
    if not spec_path.exists():
        raise SystemExit(f"YAML file not found: {spec_path}")

    payload = yaml.safe_load(spec_path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise SystemExit("YAML must decode to an object")

    for choices in REQUIRED_ONE_OF:
        if not any(payload.get(k) for k in choices):
            raise SystemExit(f"At least one of {choices} is required")

    try:
        model = InternalSampleIngestSpec.model_validate(payload)
    except ValidationError as exc:
        raise SystemExit(f"Spec validation failed:\n{exc}") from exc

    if args.check_files:
        missing: list[str] = []
        for field in FILE_FIELDS:
            value = getattr(model, field, None)
            if value in (None, "", "no_update", "NO_UPDATE"):
                continue
            path = Path(str(value))
            if not path.exists():
                missing.append(f"{field}: {value}")
        if missing:
            joined = "\n".join(missing)
            raise SystemExit(f"Referenced files missing:\n{joined}")

    print("[ok] ingest spec is valid")
    if args.json:
        print(json.dumps(model.model_dump(exclude_none=True), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
