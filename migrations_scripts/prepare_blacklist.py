#!/usr/bin/env python3
"""Convert exported blacklist records into unique allele documents without MongoDB writes."""

import argparse
import json
import sys
from pathlib import Path

from bson import json_util

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from coyote3.contracts.schemas.assay import BlacklistDoc  # noqa: E402
from coyote3.domain.dna.variant_identity import (  # noqa: E402
    build_simple_id_hash_from_simple_id,
    normalize_simple_id,
)


def prepare(records: list[dict], scopes: dict) -> tuple[list[dict], list[dict]]:
    """Combine exported exclusions, requiring explicit ownership for scalar frequencies.

    Args:
        records: Original BSON-preserving exported blacklist records.
        scopes: Old scope strings mapped to assay_group and optional asp_id. An
            explicit null asp_id retains group-only frequency evidence in the audit
            output without assigning it to an unrelated physical assay.

    Returns:
        Validated one-per-allele records and complete source evidence for review.

    Raises:
        ValueError: Identity, scope mapping or a duplicate measured frequency conflicts.
    """
    merged = {}
    evidence = []
    for source in records:
        identity = normalize_simple_id(source.get("simple_id") or source.get("pos"))
        parts = identity.split("_", 3)
        if len(parts) != 4:
            raise ValueError("Source blacklist identity must include chromosome and both alleles")
        if "assay_groups" in source:
            groups = source["assay_groups"]
            measurements = source["in_normal_perc"]
        else:
            scope = source.get("assay_group") or source.get("assay")
            if scope not in scopes:
                raise ValueError("Every old blacklist scope requires an explicit scope-map entry")
            mapping = scopes[scope]
            groups = [mapping["assay_group"]]
            assay = mapping["asp_id"]
            frequency = source.get("in_normal_perc")
            measurements = {assay: frequency} if assay and frequency is not None else {}
        candidate = BlacklistDoc(
            simple_id=identity,
            simple_id_hash=build_simple_id_hash_from_simple_id(identity),
            chrom=parts[0],
            pos=int(parts[1]),
            ref=parts[2],
            alt=parts[3],
            assay_groups=groups,
            in_normal_perc=measurements,
        ).model_dump(exclude={"id_"})
        target = merged.setdefault(
            identity, {**candidate, "assay_groups": [], "in_normal_perc": {}}
        )
        if "_id" not in target and "_id" in source:
            target["_id"] = source["_id"]
        for actor in ("created_by", "updated_by"):
            if actor not in target:
                target[actor] = source.get(actor)
            elif target[actor] != source.get(actor):
                target[actor] = None
        target["assay_groups"] = sorted(
            set(target["assay_groups"]) | set(candidate["assay_groups"])
        )
        for assay, frequency in candidate["in_normal_perc"].items():
            existing = target["in_normal_perc"].get(assay)
            if existing is not None and existing != frequency:
                raise ValueError("Conflicting normal-sample measurements require operator review")
            target["in_normal_perc"][assay] = frequency
        evidence.append({"simple_id": identity, "source_document": source})
    return [merged[key] for key in sorted(merged)], evidence


def main() -> int:
    """Read NDJSON exports and create new records plus complete source evidence.

    Returns:
        Zero after writing both files; conversion errors prevent output creation.
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--scope-map", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    evidence_path = args.output.with_suffix(".sources.ndjson")
    if args.output.exists() or evidence_path.exists():
        parser.error("Output or source-evidence file already exists; choose a new output path")
    records = [
        json_util.loads(line) for line in args.input.read_text().splitlines() if line.strip()
    ]
    prepared, evidence = prepare(records, json.loads(args.scope_map.read_text()))
    for path, documents in ((args.output, prepared), (evidence_path, evidence)):
        with path.open("x") as handle:
            for document in documents:
                handle.write(json_util.dumps(document) + "\n")
    print(f"Prepared {len(prepared)} allele exclusions from {len(records)} source records")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
