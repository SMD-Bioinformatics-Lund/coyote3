#!/usr/bin/env python3
"""Build a normalized seed bundle for collection bootstrap."""

from __future__ import annotations

import argparse
import gzip
import json
from pathlib import Path


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
        "hgnc_genes": "hgnc_genes.seed.ndjson.gz",
        "permissions": "permissions.seed.ndjson.gz",
        "refseq_canonical": "refseq_canonical.seed.ndjson.gz",
        "roles": "roles.seed.ndjson.gz",
        "vep_metadata": "vep_metadata.seed.ndjson.gz",
    }

    def load_ndjson_gzip(file_path: Path) -> list[dict]:
        docs: list[dict] = []
        with gzip.open(file_path, "rt", encoding="utf-8") as handle:
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
        file_path = path / filename
        if not file_path.exists():
            raise SystemExit(f"Missing reference seed file: {file_path}")
        payload[collection] = load_ndjson_gzip(file_path)
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
            "role",
            "assay_groups",
            "assays",
            "permissions",
            "deny_permissions",
        ),
        "asp_configs": ("aspc_id", "assay_name", "asp_group"),
        "assay_specific_panels": ("asp_id", "assay_name", "asp_group"),
        "insilico_genelists": ("isgl_id", "diagnosis", "assay_groups", "assays"),
        "blacklist": ("assay_group", "assay"),
        "samples": ("assay", "subpanel"),
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

