#!/usr/bin/env python3
"""Export DB collection contracts from Pydantic models into docs markdown."""

from __future__ import annotations

import re
import sys
from pathlib import Path
from typing import Any, get_origin

# Ensure repo root is importable when running as `python scripts/...`.
REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


def _field_type_name(annotation: Any) -> str:
    # On Python 3.10, `list[str]` / `dict[str, int]` can satisfy
    # `isinstance(annotation, type)`. Guard with `get_origin` so we don't lose
    # generic parameters and generate unstable docs across Python versions.
    if isinstance(annotation, type) and get_origin(annotation) is None:
        return annotation.__name__
    text = str(annotation)
    text = text.replace("typing.", "").replace("<class '", "").replace("'>", "")
    text = re.sub(r"^Optional\[(.+)\]$", r"\1 | None", text)
    return text


def main() -> int:
    from api.contracts.schemas.registry import COLLECTION_MODEL_ADAPTERS

    adapters = COLLECTION_MODEL_ADAPTERS
    lines: list[str] = []
    lines.append("# Collection Contracts")
    lines.append("")
    lines.append("Generated from `api/contracts/schemas/registry.py`.")
    lines.append("")
    lines.append("This is the canonical collection-key reference used by ingestion validation.")
    lines.append("")
    lines.append("## Cross-collection relations")
    lines.append("")
    lines.append(
        "- `samples.assay` must match `asp_configs.assay_name` and `assay_specific_panels.asp_id`."
    )
    lines.append("- `samples.profile` maps to ASPC lookup as `aspc_id = <assay>:<profile>`.")
    lines.append(
        "- `insilico_genelists.assays[]` and `assay_groups[]` must map to ASP/ASPC assay setup."
    )
    lines.append("- `roles.permissions[]` must reference `permissions.permission_id`.")
    lines.append("- `users.role` must reference `roles.role_id`.")
    lines.append("- `refseq_canonical.gene` should exist in `hgnc_genes.hgnc_symbol`.")
    lines.append("")
    lines.append("## DNA vs RNA sample rules")
    lines.append("")
    lines.append(
        "- `omics_layer=DNA` allows only DNA file keys: `vcf_files`, `cnv`, `cov`, `lowcov`, `biomarkers`, `transloc`."
    )
    lines.append(
        "- `omics_layer=RNA` allows only RNA file keys: `fusion_files`, `expression_path`, `classification_path`, `qc`."
    )
    lines.append("- Mixed DNA+RNA file-key payloads are rejected by model validation.")
    lines.append("")

    for collection in sorted(adapters):
        model = adapters[collection]._type  # type: ignore[attr-defined]
        fields = getattr(model, "model_fields", {})
        required = []
        optional = []
        for name, field in fields.items():
            ftype = _field_type_name(field.annotation)
            entry = f"`{name}` ({ftype})"
            if field.is_required():
                required.append(entry)
            else:
                optional.append(entry)
        lines.append(f"## `{collection}`")
        lines.append("")
        lines.append("Required keys:")
        if required:
            for item in required:
                lines.append(f"- {item}")
        else:
            lines.append("- None")
        lines.append("")
        lines.append("Optional keys:")
        if optional:
            for item in optional:
                lines.append(f"- {item}")
        else:
            lines.append("- None")
        lines.append("")

    out_path = Path("docs/api/collection-contracts.md")
    out_path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")
    print(f"[ok] wrote {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
