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
    parser.add_argument(
        "--list-files",
        action="store_true",
        help="Print resolved paths for every declared input file",
    )
    return parser.parse_args()


def main() -> int:
    from api.application.ingest.collection_writes import parse_yaml_payload
    from api.config.constants import ALL_SAMPLE_FILE_KEYS
    from api.contracts.schemas.samples import SamplesDoc

    args = parse_args()
    spec_path = Path(args.yaml)
    if not spec_path.exists():
        raise SystemExit(f"YAML file not found: {spec_path}")

    yaml_content = spec_path.read_text(encoding="utf-8")
    payload = yaml.safe_load(yaml_content)
    if not isinstance(payload, dict):
        raise SystemExit("YAML must decode to an object")

    try:
        model = SamplesDoc.model_validate(parse_yaml_payload(yaml_content))
    except (ValidationError, ValueError) as exc:
        raise SystemExit(f"Spec validation failed:\n{exc}") from exc

    resolved_files: list[tuple[str, Path]] = []
    for field in ALL_SAMPLE_FILE_KEYS:
        resource = model.files.get(field)
        if resource is None:
            continue
        path = Path(resource.path)
        if not path.is_absolute():
            path = spec_path.parent / path
        resolved_files.append((field, path.resolve()))

    if args.check_files:
        missing = [f"{field}: {path}" for field, path in resolved_files if not path.exists()]
        if missing:
            joined = "\n".join(missing)
            raise SystemExit(f"Referenced files missing:\n{joined}")

    if args.list_files:
        for _field, path in resolved_files:
            print(path)
        return 0

    print("[ok] ingest spec is valid")
    if args.json:
        print(
            json.dumps(
                model.model_dump(mode="json", exclude_none=True),
                indent=2,
                sort_keys=True,
            )
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
