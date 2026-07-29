#!/usr/bin/env python3
"""Build a normalized seed bundle for collection bootstrap."""

from __future__ import annotations

import argparse
import gzip
import json
import re
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from api.config.constants import (  # noqa: E402
    ALL_SAMPLE_FILE_KEYS,
    SUBPANEL_BASE_ID,
    normalize_environment,
)


def _normalize_permission_id(permission_id) -> str:
    """Normalize a permission identifier for seed output."""
    return str(permission_id or "").strip().lower()


def _normalize_permission_ids(permission_ids) -> list[str]:
    """Normalize and deduplicate permission identifiers."""
    normalized: list[str] = []
    seen: set[str] = set()
    if permission_ids is None:
        return normalized
    if isinstance(permission_ids, (str, bytes)):
        permission_ids = [permission_ids]
    for permission_id in permission_ids:
        normalized_id = _normalize_permission_id(permission_id)
        if normalized_id and normalized_id not in seen:
            normalized.append(normalized_id)
            seen.add(normalized_id)
    return normalized


def _clean_identifier(value, *, default: str = SUBPANEL_BASE_ID) -> str:
    """Normalize seed identifiers to the canonical contract-safe character set."""
    text = str(value or "").strip()
    text = text.replace(":", "_").replace(" ", "_")
    text = re.sub(r"[^A-Za-z0-9_-]+", "_", text).strip("_")
    return text or default


def _normalize_username(value) -> str:
    """Convert fixture usernames into contract-safe local usernames."""
    text = str(value or "").strip().lower()
    if "@" in text:
        text = text.split("@", 1)[0]
    text = re.sub(r"[^a-z0-9_.-]+", ".", text).strip(".")
    return text or "seed.user"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seed-source", required=True, help="Directory with *.json seed files")
    parser.add_argument("--dest-dir", required=True, help="Output directory for normalized seed")
    parser.add_argument("--seed-actor", required=True, help="created_by/updated_by stamp value")
    parser.add_argument("--seed-time", required=True, help="created_on/updated_on stamp value")
    parser.add_argument(
        "--reference-seed-data",
        default="",
        help="Optional directory with compressed reference seed packs",
    )
    return parser.parse_args()


def load_seed(path: Path) -> dict[str, list[dict]]:
    payload: dict[str, list[dict]] = {}
    for file in sorted(path.glob("*.json")):
        value = json.loads(file.read_text(encoding="utf-8"))
        if not isinstance(value, list):
            raise SystemExit(f"Collection seed file must contain a JSON list: {file}")
        payload[file.stem] = value
    return payload


def load_reference_seed_pack(path: Path) -> dict[str, list[dict]]:
    required_pack = {
        "hgnc_genes": "hgnc_genes.seed.ndjson",
        "permissions": "permissions.seed.ndjson",
        "refseq_canonical": "refseq_canonical.seed.ndjson",
        "roles": "roles.seed.ndjson",
        "vep_metadata": "vep_metadata.seed.ndjson",
    }

    def resolve_reference_file(base_dir: Path, stem_name: str) -> Path:
        plain_path = base_dir / stem_name
        if plain_path.exists():
            return plain_path
        gzip_path = base_dir / f"{stem_name}.gz"
        if gzip_path.exists():
            return gzip_path
        raise SystemExit(f"Missing reference seed file: {plain_path} or {gzip_path}")

    def load_ndjson(file_path: Path) -> list[dict]:
        docs: list[dict] = []
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

    payload: dict[str, list[dict]] = {}
    for collection, filename in required_pack.items():
        file_path = resolve_reference_file(path, filename)
        payload[collection] = load_ndjson(file_path)
    return payload


def normalize_extended_json(value):
    if isinstance(value, dict):
        if set(value.keys()) == {"$date"}:
            return value.get("$date")
        if set(value.keys()) == {"$oid"}:
            return value.get("$oid")
        return {k: normalize_extended_json(v) for k, v in value.items()}
    if isinstance(value, list):
        return [normalize_extended_json(v) for v in value]
    return value


def lower_business_keys(seed: dict[str, list[dict]]) -> None:
    lowercase_fields = {
        "permissions": ("permission_id",),
        "roles": ("role_id",),
        "users": (
            "username",
            "email",
            "roles",
            "asp_groups",
            "asp_ids",
        ),
        "asp_configs": ("aspc_id", "asp_id", "subpanel_id", "asp_group"),
        "assay_specific_panels": ("asp_id", "assay_name", "asp_group"),
        "insilico_genelists": ("isgl_id", "diagnosis", "asp_groups", "asp_ids"),
        "blacklist": ("assay_group", "assay"),
        "samples": ("asp_id", "subpanel_id", "environment", "platform"),
    }

    def normalize_item(value):
        if isinstance(value, str):
            return value.strip().lower()
        if isinstance(value, list):
            return [normalize_item(item) for item in value]
        return value

    for collection, fields in lowercase_fields.items():
        for doc in seed.get(collection, []) or []:
            if not isinstance(doc, dict):
                continue
            for field in fields:
                if field in doc and doc[field] is not None:
                    doc[field] = normalize_item(doc[field])


def canonicalize_permission_fields(seed: dict[str, list[dict]]) -> None:
    for doc in seed.get("permissions", []) or []:
        if not isinstance(doc, dict):
            continue
        permission_id = _normalize_permission_id(
            doc.get("permission_id") or doc.get("permission_name")
        )
        if permission_id:
            doc["permission_id"] = permission_id
        doc.pop("permission_name", None)

    for doc in seed.get("roles", []) or []:
        if not isinstance(doc, dict):
            continue
        if "permissions" in doc:
            doc["permissions"] = _normalize_permission_ids(doc.get("permissions"))
        doc.pop("deny_permissions", None)

    for doc in seed.get("users", []) or []:
        if not isinstance(doc, dict):
            continue
        if "username" in doc:
            doc["username"] = _normalize_username(doc.get("username"))


def canonicalize_assay_config_fields(seed: dict[str, list[dict]]) -> None:
    for doc in seed.get("asp_configs", []) or []:
        if not isinstance(doc, dict):
            continue

        asp_id = _clean_identifier(doc.get("asp_id"), default="assay")
        subpanel_id = _clean_identifier(doc.get("subpanel_id") or SUBPANEL_BASE_ID)
        environment = normalize_environment(doc.get("environment") or "production")

        doc["asp_id"] = asp_id
        doc["subpanel_id"] = subpanel_id
        doc["environment"] = environment
        doc["aspc_id"] = _clean_identifier(
            f"{asp_id}_{subpanel_id}_{environment}", default=f"assay_{environment}"
        )

        retired = {"assay_name", "query", "subpanel", "genelists", "cnv_genelists"}
        present = sorted(retired.intersection(doc))
        if present:
            raise ValueError(f"asp_configs seed uses retired fields: {', '.join(present)}")


def canonicalize_sample_fields(seed: dict[str, list[dict]]) -> None:
    for doc in seed.get("samples", []) or []:
        if not isinstance(doc, dict):
            continue
        retired = {"assay", "profile", "subpanel", "sequencing_technology"}
        present = sorted(retired.intersection(doc))
        if present:
            raise ValueError(f"samples seed uses retired fields: {', '.join(present)}")
        if "environment" in doc:
            doc["environment"] = normalize_environment(doc.get("environment"))
        if "omics_layer" in doc and isinstance(doc.get("omics_layer"), str):
            doc["omics_layer"] = doc["omics_layer"].strip().lower()
        if "platform" in doc and isinstance(doc.get("platform"), str):
            doc["platform"] = doc["platform"].strip().lower()

        files = doc.get("files") if isinstance(doc.get("files"), dict) else {}
        for file_key in ALL_SAMPLE_FILE_KEYS:
            if file_key not in doc:
                continue
            raw_file = doc.pop(file_key)
            if raw_file in (None, ""):
                continue
            files[file_key] = raw_file if isinstance(raw_file, dict) else {"path": raw_file}
        doc["files"] = files

        for legacy_key in (
            "comments",
            "reports",
            "groups",
            "report_num",
            "data_counts",
            "ingest_status",
        ):
            doc.pop(legacy_key, None)


def canonicalize_seed_contract(seed: dict[str, list[dict]]) -> None:
    canonicalize_permission_fields(seed)
    canonicalize_assay_config_fields(seed)
    canonicalize_sample_fields(seed)


def stamp_docs(seed: dict[str, list[dict]], seed_actor: str, seed_time: str) -> None:
    for docs in seed.values():
        if not isinstance(docs, list):
            continue
        for idx, doc in enumerate(docs):
            if not isinstance(doc, dict):
                continue
            normalized_doc = normalize_extended_json(doc)
            docs[idx] = normalized_doc
            normalized_doc["created_by"] = seed_actor
            normalized_doc["updated_by"] = seed_actor
            normalized_doc["created_on"] = seed_time
            normalized_doc["updated_on"] = seed_time


def main() -> int:
    args = parse_args()
    source = Path(args.seed_source)
    dest_dir = Path(args.dest_dir)
    reference_seed_data = Path(args.reference_seed_data) if args.reference_seed_data else None

    if not source.is_dir():
        raise SystemExit(f"Seed source not found: {source}")
    dest_dir.mkdir(parents=True, exist_ok=True)

    seed = load_seed(source)
    if reference_seed_data is not None:
        seed.update(load_reference_seed_pack(reference_seed_data))
    canonicalize_seed_contract(seed)
    lower_business_keys(seed)
    stamp_docs(seed, args.seed_actor, args.seed_time)

    for collection, docs in seed.items():
        (dest_dir / f"{collection}.json").write_text(
            json.dumps(docs, ensure_ascii=False), encoding="utf-8"
        )

    print(f"[ok] normalized seed bundle: {dest_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
