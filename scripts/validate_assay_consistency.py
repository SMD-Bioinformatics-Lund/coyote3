#!/usr/bin/env python3
"""Validate assay and assay-group consistency across seed collections."""

from __future__ import annotations

import argparse
import gzip
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

import yaml
from pydantic import ValidationError

# Ensure repo root is importable when running as `python scripts/...`.
REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from api.contracts.schemas.registry import (  # noqa: E402
    supported_collections,
    validate_collection_document,
)

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
    "refseq_canonical",
    "hgnc_genes",
    "vep_metadata",
    "asp_configs",
    "assay_specific_panels",
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
    parser.add_argument(
        "--reference-seed-data",
        help="Optional directory with compressed NDJSON seed packs",
    )
    parser.add_argument(
        "--validate-all-contracts",
        action="store_true",
        help="Validate every registered collection contract found in seed directory.",
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


def _load_reference_seed_pack(path: str) -> dict[str, Any]:
    reference_path = Path(path)
    if not reference_path.is_dir():
        raise SystemExit(f"Reference seed data directory not found: {reference_path}")

    required_pack = {
        "hgnc_genes": "hgnc_genes.seed.ndjson",
        "permissions": "permissions.seed.ndjson",
        "refseq_canonical": "refseq_canonical.seed.ndjson",
        "roles": "roles.seed.ndjson",
        "vep_metadata": "vep_metadata.seed.ndjson",
    }

    def _resolve_reference_file(base_dir: Path, stem_name: str) -> Path:
        plain_path = base_dir / stem_name
        if plain_path.exists():
            return plain_path
        gzip_path = base_dir / f"{stem_name}.gz"
        if gzip_path.exists():
            return gzip_path
        raise SystemExit(f"Missing reference seed file: {plain_path} or {gzip_path}")

    def _load_ndjson(file_path: Path) -> list[dict[str, Any]]:
        docs: list[dict[str, Any]] = []
        opener = gzip.open if file_path.suffix == ".gz" else open
        with opener(file_path, "rt", encoding="utf-8") as handle:
            for line in handle:
                text = line.strip()
                if not text:
                    continue
                value = json.loads(text)
                if not isinstance(value, dict):
                    raise SystemExit(
                        f"Reference seed file must contain JSON objects per line: {file_path}"
                    )
                docs.append(value)
        return docs

    payload: dict[str, Any] = {}
    for collection, filename in required_pack.items():
        file_path = _resolve_reference_file(reference_path, filename)
        payload[collection] = _load_ndjson(file_path)

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


def _validate_registered_contracts(
    seed: dict[str, Any], *, validate_all_contracts: bool = False
) -> list[str]:
    errors: list[str] = []
    registered = set(supported_collections())
    if validate_all_contracts:
        collections_to_validate = {name for name in seed if name in registered}
    else:
        collections_to_validate = {
            name for name in REQUIRED_BASELINE_COLLECTIONS if name in seed and name in registered
        }
    for collection, docs in sorted(seed.items()):
        if collection not in collections_to_validate:
            continue
        for idx, doc in enumerate(docs):
            try:
                validate_collection_document(collection, doc)
            except ValidationError as exc:
                errors.append(f"{collection}[{idx}] fails contract validation: {exc}")
            except (
                Exception
            ) as exc:  # pragma: no cover - defensive guard for unexpected model errors
                errors.append(f"{collection}[{idx}] fails contract validation: {exc}")
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


def _validate_lowercase_business_ids(seed: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    field_rules: dict[str, tuple[str, ...]] = {
        "permissions": ("permission_id",),
        "roles": ("role_id",),
        "users": ("username", "email", "roles", "assay_groups", "assays"),
        "asp_configs": ("aspc_id", "assay_name", "asp_group"),
        "assay_specific_panels": ("asp_id", "assay_name", "asp_group"),
        "insilico_genelists": ("isgl_id", "diagnosis", "assay_groups", "assays"),
        "blacklist": ("assay_group", "assay"),
        "samples": ("assay", "subpanel"),
    }

    def _append_error(collection: str, idx: int, field: str, value: str) -> None:
        errors.append(
            f"{collection}[{idx}] field '{field}' must be lowercase for business-key consistency: '{value}'"
        )

    for collection, fields in field_rules.items():
        for idx, doc in enumerate(seed.get(collection, [])):
            if not isinstance(doc, dict):
                continue
            for field in fields:
                value = doc.get(field)
                if value is None:
                    continue
                items = value if isinstance(value, list) else [value]
                for item in items:
                    normalized = _norm(item)
                    if not normalized:
                        continue
                    if normalized != normalized.lower():
                        _append_error(collection, idx, field, normalized)
    return errors


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
        for role in user_doc.get("roles", []) or []:
            normalized_role = _norm(role)
            if normalized_role and normalized_role not in role_ids:
                errors.append(f"users[{idx}] references unknown role '{normalized_role}'")
        for group in user_doc.get("assay_groups", []) or []:
            if _norm(group) and _norm(group) not in assay_groups:
                errors.append(f"users[{idx}] references unknown assay_group '{_norm(group)}'")
        for assay in user_doc.get("assays", []) or []:
            if _norm(assay) and _norm(assay) not in assays:
                errors.append(f"users[{idx}] references unknown assay '{_norm(assay)}'")

    return errors


def main() -> int:
    args = parse_args()
    seed = _load_seed(args.seed_file)
    if args.reference_seed_data:
        seed.update(_load_reference_seed_pack(args.reference_seed_data))
    shape_errors = _validate_contract_shaping(seed)
    if shape_errors:
        raise SystemExit("Seed contract-shape errors:\n- " + "\n- ".join(shape_errors))

    contract_errors = _validate_registered_contracts(
        seed,
        validate_all_contracts=bool(args.validate_all_contracts),
    )
    if contract_errors:
        raise SystemExit("Seed contract model errors:\n- " + "\n- ".join(contract_errors))

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

    lowercase_errors = _validate_lowercase_business_ids(seed)
    if lowercase_errors:
        raise SystemExit("Lowercase business-key errors:\n- " + "\n- ".join(lowercase_errors))

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
