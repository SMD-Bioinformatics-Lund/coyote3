#!/usr/bin/env python3
"""Validate assay and assay-group consistency across seed collections."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

import yaml

# Ensure repo root is importable when running as `python scripts/...`.
REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

VALID_ENVIRONMENTS = {"production", "development", "testing", "validation"}
ENV_ALIASES = {
    "prod": "production",
    "production": "production",
    "dev": "development",
    "development": "development",
    "test": "testing",
    "testing": "testing",
    "validation": "validation",
    "stage": "validation",
    "staging": "validation",
}
REQUIRED_BASELINE_COLLECTIONS = (
    "permissions",
    "roles",
    "asp_configs",
    "assay_specific_panels",
    "insilico_genelists",
    "refseq_canonical",
    "hgnc_genes",
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Validate assay references in center seed JSON and optional sample YAML."
    )
    parser.add_argument(
        "--seed-file",
        required=True,
        help="Seed directory path containing <collection>.json files",
    )
    parser.add_argument(
        "--yaml", help="Optional sample ingest YAML to validate assay against seeds"
    )
    return parser.parse_args()


def _norm(value: Any) -> str:
    return str(value).strip()


def _load_seed(path: str) -> dict[str, Any]:
    seed_path = Path(path)
    if not seed_path.is_dir():
        raise SystemExit(f"Seed directory not found: {seed_path}")
    payload: dict[str, Any] = {}
    for file in sorted(seed_path.glob("*.json")):
        value = json.loads(file.read_text(encoding="utf-8"))
        if not isinstance(value, list):
            raise SystemExit(f"Collection seed file must contain a JSON list: {file}")
        payload[file.stem] = value
    return payload


def _is_iso_datetime(value: str) -> bool:
    text = value.strip()
    if not text:
        return False
    # Accept UTC "Z" form in addition to datetime.fromisoformat native forms.
    if text.endswith("Z"):
        text = f"{text[:-1]}+00:00"
    try:
        datetime.fromisoformat(text)
        return True
    except ValueError:
        return False


def _contains_extended_json_dates(value: Any) -> bool:
    if isinstance(value, dict):
        if set(value.keys()) == {"$date"}:
            return True
        if set(value.keys()) == {"$oid"}:
            return True
        return any(_contains_extended_json_dates(v) for v in value.values())
    if isinstance(value, list):
        return any(_contains_extended_json_dates(v) for v in value)
    return False


def _validate_contract_shaping(seed: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    for collection, docs in sorted(seed.items()):
        if not isinstance(docs, list):
            errors.append(f"{collection} must be a JSON array of objects")
            continue
        for idx, doc in enumerate(docs):
            if not isinstance(doc, dict):
                errors.append(f"{collection}[{idx}] must be a JSON object")
                continue
            if _contains_extended_json_dates(doc):
                errors.append(
                    f"{collection}[{idx}] contains Extended JSON wrappers ($date/$oid); "
                    "use plain JSON scalar values in seed files"
                )
            for dt_key in ("created_on", "updated_on"):
                if dt_key in doc and doc[dt_key] is not None:
                    if not isinstance(doc[dt_key], str) or not _is_iso_datetime(doc[dt_key]):
                        errors.append(
                            f"{collection}[{idx}].{dt_key} must be an ISO-8601 datetime string"
                        )
            if (
                "version" in doc
                and doc["version"] is not None
                and not isinstance(doc["version"], (int, float))
            ):
                errors.append(f"{collection}[{idx}].version must be numeric")
            history = doc.get("version_history")
            if history is not None:
                if not isinstance(history, list):
                    errors.append(f"{collection}[{idx}].version_history must be a list")
                    continue
                for hidx, entry in enumerate(history):
                    if not isinstance(entry, dict):
                        errors.append(
                            f"{collection}[{idx}].version_history[{hidx}] must be an object"
                        )
                        continue
                    ts = entry.get("updated_on")
                    if ts is not None and (not isinstance(ts, str) or not _is_iso_datetime(ts)):
                        errors.append(
                            f"{collection}[{idx}].version_history[{hidx}].updated_on "
                            "must be an ISO-8601 datetime string"
                        )
    return errors


def _known_assays(seed: dict[str, Any]) -> set[str]:
    assays: set[str] = set()
    for doc in seed.get("asp_configs", []):
        if isinstance(doc, dict):
            name = _norm(doc.get("assay_name", ""))
            if name:
                assays.add(name)
            aspc_id = _norm(doc.get("aspc_id", ""))
            if ":" in aspc_id:
                assays.add(_norm(aspc_id.split(":", 1)[0]))
    for doc in seed.get("assay_specific_panels", []):
        if isinstance(doc, dict):
            for key in ("asp_id", "assay_name"):
                value = _norm(doc.get(key, ""))
                if value:
                    assays.add(value)
    for doc in seed.get("insilico_genelists", []):
        if isinstance(doc, dict):
            for assay in doc.get("assays", []) or []:
                value = _norm(assay)
                if value:
                    assays.add(value)
    return assays


def _known_assay_groups(seed: dict[str, Any]) -> set[str]:
    groups: set[str] = set()
    for collection in ("asp_configs", "assay_specific_panels"):
        for doc in seed.get(collection, []):
            if isinstance(doc, dict):
                value = _norm(doc.get("asp_group", ""))
                if value:
                    groups.add(value)
    for doc in seed.get("insilico_genelists", []):
        if isinstance(doc, dict):
            for group in doc.get("assay_groups", []) or []:
                value = _norm(group)
                if value:
                    groups.add(value)
    return groups


def _collect_references(seed: dict[str, Any]) -> tuple[set[str], set[str]]:
    assays: set[str] = set()
    groups: set[str] = set()

    for doc in seed.get("samples", []):
        if isinstance(doc, dict):
            value = _norm(doc.get("assay", ""))
            if value:
                assays.add(value)

    for doc in seed.get("blacklist", []):
        if isinstance(doc, dict):
            value = _norm(doc.get("assay", ""))
            if value:
                assays.add(value)

    for doc in seed.get("insilico_genelists", []):
        if not isinstance(doc, dict):
            continue
        for assay in doc.get("assays", []) or []:
            value = _norm(assay)
            if value:
                assays.add(value)
        for group in doc.get("assay_groups", []) or []:
            value = _norm(group)
            if value:
                groups.add(value)

    return assays, groups


def _normalize_env(value: Any) -> str:
    raw = _norm(value).lower()
    return ENV_ALIASES.get(raw, raw)


def _collect_assay_group_map(seed: dict[str, Any]) -> dict[str, set[str]]:
    mapping: dict[str, set[str]] = {}
    for collection in ("asp_configs", "assay_specific_panels"):
        for doc in seed.get(collection, []):
            if not isinstance(doc, dict):
                continue
            assay = _norm(doc.get("assay_name") or doc.get("asp_id") or "")
            group = _norm(doc.get("asp_group", ""))
            if assay and group:
                mapping.setdefault(assay, set()).add(group)
    return mapping


def _validate_aspc(seed: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    seen_ids: set[str] = set()
    for idx, doc in enumerate(seed.get("asp_configs", [])):
        if not isinstance(doc, dict):
            errors.append(f"asp_configs[{idx}] must be an object")
            continue
        aspc_id = _norm(doc.get("aspc_id", ""))
        assay_name = _norm(doc.get("assay_name", ""))
        environment = _normalize_env(doc.get("environment", ""))

        if not aspc_id or ":" not in aspc_id:
            errors.append(
                f"asp_configs[{idx}] has invalid aspc_id '{aspc_id}' (expected assay:environment)"
            )
            continue

        assay_from_id, env_from_id = aspc_id.split(":", 1)
        assay_from_id = _norm(assay_from_id)
        env_from_id = _normalize_env(env_from_id)

        if aspc_id in seen_ids:
            errors.append(f"Duplicate asp_configs.aspc_id '{aspc_id}'")
        seen_ids.add(aspc_id)

        if assay_name and assay_name != assay_from_id:
            errors.append(
                f"asp_configs[{idx}] mismatch: assay_name '{assay_name}' != aspc_id assay '{assay_from_id}'"
            )
        if environment and environment != env_from_id:
            errors.append(
                f"asp_configs[{idx}] mismatch: environment '{environment}' != aspc_id environment '{env_from_id}'"
            )

        if env_from_id not in VALID_ENVIRONMENTS:
            errors.append(
                f"asp_configs[{idx}] invalid environment '{env_from_id}' in aspc_id '{aspc_id}'"
            )
        if environment and environment not in VALID_ENVIRONMENTS:
            errors.append(f"asp_configs[{idx}] invalid environment '{environment}'")
        if "is_active" not in doc or not isinstance(doc.get("is_active"), bool):
            errors.append(f"asp_configs[{idx}] must include boolean is_active")
    return errors


def _validate_panels(seed: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    for idx, doc in enumerate(seed.get("assay_specific_panels", [])):
        if not isinstance(doc, dict):
            errors.append(f"assay_specific_panels[{idx}] must be an object")
            continue
        if "is_active" not in doc or not isinstance(doc.get("is_active"), bool):
            errors.append(f"assay_specific_panels[{idx}] must include boolean is_active")
    return errors


def _validate_isgl(
    seed: dict[str, Any], known_assays: set[str], known_groups: set[str]
) -> list[str]:
    errors: list[str] = []
    assay_to_groups = _collect_assay_group_map(seed)
    for idx, doc in enumerate(seed.get("insilico_genelists", [])):
        if not isinstance(doc, dict):
            errors.append(f"insilico_genelists[{idx}] must be an object")
            continue
        assays = [_norm(a) for a in (doc.get("assays", []) or []) if _norm(a)]
        groups = [_norm(g) for g in (doc.get("assay_groups", []) or []) if _norm(g)]
        if "is_active" not in doc or not isinstance(doc.get("is_active"), bool):
            errors.append(f"insilico_genelists[{idx}] must include boolean is_active")

        if not assays:
            errors.append(f"insilico_genelists[{idx}] has empty assays list")
        if not groups:
            errors.append(f"insilico_genelists[{idx}] has empty assay_groups list")

        for assay in assays:
            if assay not in known_assays:
                errors.append(f"insilico_genelists[{idx}] references unknown assay '{assay}'")

        for group in groups:
            if group not in known_groups:
                errors.append(f"insilico_genelists[{idx}] references unknown assay_group '{group}'")

        # If mapping exists for assay->groups, require overlap with stated isgl groups.
        for assay in assays:
            mapped_groups = assay_to_groups.get(assay, set())
            if mapped_groups and not (mapped_groups & set(groups)):
                errors.append(
                    f"insilico_genelists[{idx}] assay '{assay}' does not match its configured asp_group(s) "
                    f"{sorted(mapped_groups)}"
                )
    return errors


def _validate_yaml_assay(yaml_path: str, known_assays: set[str]) -> None:
    payload = yaml.safe_load(Path(yaml_path).read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise SystemExit("YAML must decode to an object")
    yaml_assay = _norm(payload.get("assay", ""))
    if yaml_assay and yaml_assay not in known_assays:
        known = ", ".join(sorted(known_assays)) or "(none)"
        raise SystemExit(
            f"YAML assay '{yaml_assay}' is not declared in seed core collections. Known assays: {known}"
        )


def _validate_bootstrap_dependencies(seed: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    for collection in REQUIRED_BASELINE_COLLECTIONS:
        value = seed.get(collection)
        if not isinstance(value, list) or not value:
            errors.append(
                f"Required collection '{collection}' must be present with at least one document"
            )

    permission_ids = {
        _norm(doc.get("permission_id", ""))
        for doc in seed.get("permissions", [])
        if isinstance(doc, dict) and _norm(doc.get("permission_id", ""))
    }
    role_ids = {
        _norm(doc.get("role_id", ""))
        for doc in seed.get("roles", [])
        if isinstance(doc, dict) and _norm(doc.get("role_id", ""))
    }
    assay_groups = _known_assay_groups(seed)
    assays = _known_assays(seed)
    for idx, role_doc in enumerate(seed.get("roles", [])):
        if not isinstance(role_doc, dict):
            continue
        for perm in role_doc.get("permissions", []) or []:
            if _norm(perm) and _norm(perm) not in permission_ids:
                errors.append(f"roles[{idx}] references unknown permission '{_norm(perm)}'")

    for idx, user_doc in enumerate(seed.get("users", [])):
        if not isinstance(user_doc, dict):
            continue
        role = _norm(user_doc.get("role", ""))
        if role and role not in role_ids:
            errors.append(f"users[{idx}] references unknown role '{role}'")
        for group in user_doc.get("assay_groups", []) or []:
            if _norm(group) and _norm(group) not in assay_groups:
                errors.append(f"users[{idx}] references unknown assay_group '{_norm(group)}'")
        for assay in user_doc.get("assays", []) or []:
            if _norm(assay) and _norm(assay) not in assays:
                errors.append(f"users[{idx}] references unknown assay '{_norm(assay)}'")

    refseq_genes = {
        _norm(doc.get("gene", ""))
        for doc in seed.get("refseq_canonical", [])
        if isinstance(doc, dict) and _norm(doc.get("gene", ""))
    }
    hgnc_symbols = {
        _norm(doc.get("hgnc_symbol", ""))
        for doc in seed.get("hgnc_genes", [])
        if isinstance(doc, dict) and _norm(doc.get("hgnc_symbol", ""))
    }
    missing_symbols = sorted(refseq_genes - hgnc_symbols)
    if missing_symbols:
        errors.append(
            "refseq_canonical contains genes missing in hgnc_genes.hgnc_symbol: "
            + ", ".join(missing_symbols)
        )

    return errors


def main() -> int:
    args = parse_args()
    seed = _load_seed(args.seed_file)
    shape_errors = _validate_contract_shaping(seed)
    if shape_errors:
        raise SystemExit("Seed contract-shape errors:\n- " + "\n- ".join(shape_errors))

    known_assays = _known_assays(seed)
    known_groups = _known_assay_groups(seed)
    referenced_assays, referenced_groups = _collect_references(seed)

    if not known_assays:
        raise SystemExit(
            "No assays discovered from asp_configs/assay_specific_panels/insilico_genelists in seed."
        )

    unknown_assays = sorted(referenced_assays - known_assays)
    if unknown_assays:
        raise SystemExit(
            "Unknown assay references in seed: "
            + ", ".join(unknown_assays)
            + ". Add these assays to core config collections first."
        )

    unknown_groups = sorted(referenced_groups - known_groups)
    if unknown_groups:
        raise SystemExit(
            "Unknown assay group references in seed: "
            + ", ".join(unknown_groups)
            + ". Add these groups to core config collections first."
        )

    aspc_errors = _validate_aspc(seed)
    if aspc_errors:
        raise SystemExit("ASPC consistency errors:\n- " + "\n- ".join(aspc_errors))

    panel_errors = _validate_panels(seed)
    if panel_errors:
        raise SystemExit("ASP consistency errors:\n- " + "\n- ".join(panel_errors))

    isgl_errors = _validate_isgl(seed, known_assays, known_groups)
    if isgl_errors:
        raise SystemExit("ISGL consistency errors:\n- " + "\n- ".join(isgl_errors))

    dependency_errors = _validate_bootstrap_dependencies(seed)
    if dependency_errors:
        raise SystemExit("Bootstrap dependency errors:\n- " + "\n- ".join(dependency_errors))

    if args.yaml:
        _validate_yaml_assay(args.yaml, known_assays)

    print("[ok] assay consistency checks passed")
    print(f"[info] known assays: {', '.join(sorted(known_assays))}")
    print(f"[info] known assay groups: {', '.join(sorted(known_groups))}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
