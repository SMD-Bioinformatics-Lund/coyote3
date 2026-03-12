"""Collection-shaped fixture documents backed by read-only DB snapshots.

Source of truth:
- prod latest docs for all collections
- dev latest docs scoped to RNA/WGS patterns for RNA/WGS-sensitive fixtures

Fallback defaults are preserved so tests remain deterministic when snapshot docs
are missing specific fields.
"""

from __future__ import annotations

from copy import deepcopy
from pathlib import Path
import json
from typing import Any

from api.security.access import ApiUser


SNAPSHOT_DIR = Path(__file__).resolve().parent / "db_snapshots"
PROD_SNAPSHOT_PATH = SNAPSHOT_DIR / "prod_latest.json"
DEV_RNA_WGS_SNAPSHOT_PATH = SNAPSHOT_DIR / "dev_rna_wgs_latest.json"


def _load_snapshot(path: Path) -> dict[str, Any]:
    """Handle  load snapshot.

    Args:
            path: Path.

    Returns:
            The  load snapshot result.
    """
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        return payload.get("collections", {})
    except Exception:
        return {}


_PROD = _load_snapshot(PROD_SNAPSHOT_PATH)
_DEV_RNA_WGS = _load_snapshot(DEV_RNA_WGS_SNAPSHOT_PATH)


def _latest_doc(collection_alias: str, *, prefer_dev_rna_wgs: bool = False) -> dict[str, Any] | None:
    """Handle  latest doc.

    Args:
            collection_alias: Collection alias.
            prefer_dev_rna_wgs: Prefer dev rna wgs. Keyword-only argument.

    Returns:
            The  latest doc result.
    """
    pools = [_DEV_RNA_WGS, _PROD] if prefer_dev_rna_wgs else [_PROD, _DEV_RNA_WGS]
    for pool in pools:
        meta = pool.get(collection_alias) or {}
        docs = meta.get("docs")
        if isinstance(docs, list) and docs and isinstance(docs[0], dict):
            return deepcopy(docs[0])
        latest = meta.get("latest")
        if isinstance(latest, dict):
            return deepcopy(latest)
    return None


def _with_defaults(doc: dict[str, Any] | None, defaults: dict[str, Any]) -> dict[str, Any]:
    """Handle  with defaults.

    Args:
            doc: Doc.
            defaults: Defaults.

    Returns:
            The  with defaults result.
    """
    merged = deepcopy(defaults)
    if not isinstance(doc, dict):
        return merged

    def rec(dst: dict[str, Any], src: dict[str, Any]) -> None:
        """Handle rec.

        Args:
            dst (dict[str, Any]): Value for ``dst``.
            src (dict[str, Any]): Value for ``src``.

        Returns:
            None.
        """
        for k, v in src.items():
            if isinstance(v, dict) and isinstance(dst.get(k), dict):
                rec(dst[k], v)
            else:
                dst[k] = v

    rec(merged, doc)
    return merged


def user_doc() -> dict:
    """Handle user doc.

    Returns:
        dict: The function result.
    """
    defaults = {
        "_id": "u1",
        "user_id": "u1",
        "email": "tester@example.com",
        "fullname": "Test User",
        "username": "tester",
        "role": "admin",
        "access_level": 99999,
        "permissions": ["preview_report", "create_report", "view_role", "edit_sample"],
        "deny_permissions": [],
        "assays": ["WGS", "RNA_PANEL"],
        "assay_groups": ["dna", "rna"],
        "envs": ["production"],
        "asp_map": {"DNA": {"PANEL": {"dna": ["WGS"]}}},
    }
    # users are sourced through roles/users collections; keep stable defaults.
    return _with_defaults(None, defaults)


def api_user() -> ApiUser:
    """Handle api user.

    Returns:
        ApiUser: The function result.
    """
    doc = user_doc()
    return ApiUser(
        id=str(doc.get("_id") or "u1"),
        email=str(doc.get("email") or "tester@example.com"),
        fullname=str(doc.get("fullname") or "Test User"),
        username=str(doc.get("username") or "tester"),
        role=str(doc.get("role") or "admin"),
        access_level=int(doc.get("access_level") or 99),
        permissions=list(doc.get("permissions") or []),
        denied_permissions=list(doc.get("deny_permissions") or []),
        assays=list(doc.get("assays") or []),
        assay_groups=list(doc.get("assay_groups") or []),
        envs=list(doc.get("envs") or []),
        asp_map=deepcopy(doc.get("asp_map") or {}),
    )


def sample_doc(*, prefer_dev_rna_wgs: bool = False) -> dict:
    """Handle sample doc.

    Args:
        prefer_dev_rna_wgs (bool): Value for ``prefer_dev_rna_wgs``.

    Returns:
        dict: The function result.
    """
    defaults = {
        "_id": "s1",
        "name": "SAMPLE_001",
        "assay": "WGS",
        "profile": "production",
        "case_id": "CASE001",
        "control_id": "CTRL001",
        "subpanel": "myeloid",
        "vep": 110,
        "report_num": 2,
        "reports": [{"_id": "r1", "report_id": "RID1", "report_num": 1, "time_created": 1}],
        "case": {"clarity_id": "CLARITY_CASE_001"},
        "control": {"clarity_id": "CLARITY_CTRL_001"},
        "filters": {
            "max_freq": 1.0,
            "min_freq": 0.05,
            "max_control_freq": 0.2,
            "min_depth": 100,
            "min_alt_reads": 5,
            "max_popfreq": 0.01,
            "vep_consequences": ["missense_variant"],
            "genelists": ["gl1"],
            "adhoc_genes": {"label": "focus", "genes": ["TP53", "NPM1"]},
        },
    }
    doc = _latest_doc("samples_collection", prefer_dev_rna_wgs=prefer_dev_rna_wgs)
    return _with_defaults(doc, defaults)


def assay_config_doc(*, prefer_dev_rna_wgs: bool = False) -> dict:
    """Handle assay config doc.

    Args:
        prefer_dev_rna_wgs (bool): Value for ``prefer_dev_rna_wgs``.

    Returns:
        dict: The function result.
    """
    defaults = {
        "_id": "aspc1",
        "schema_name": "aspc_schema_v1",
        "asp_group": "dna",
        "analysis_types": ["SNV", "CNV", "BIOMARKER"],
        "filters": deepcopy(sample_doc(prefer_dev_rna_wgs=prefer_dev_rna_wgs).get("filters", {})),
        "reporting": {"report_path": "dna_report.html", "plots_path": "reports/plots"},
        "verification_samples": {"SAMPLE": ["1:1:A:T"]},
    }
    doc = _latest_doc("aspc_collection", prefer_dev_rna_wgs=prefer_dev_rna_wgs)
    return _with_defaults(doc, defaults)


def variant_doc(*, prefer_dev_rna_wgs: bool = False) -> dict:
    """Handle variant doc.

    Args:
        prefer_dev_rna_wgs (bool): Value for ``prefer_dev_rna_wgs``.

    Returns:
        dict: The function result.
    """
    defaults = {
        "_id": "v1",
        "SAMPLE_ID": "s1",
        "CHROM": "17",
        "POS": 7579472,
        "REF": "C",
        "ALT": "T",
        "simple_id": "17_7579472_C_T",
        "simple_id_hash": "hash_17_7579472_C_T",
        "transcripts": ["ENST00000269305"],
        "INFO": {
            "selected_CSQ": {
                "SYMBOL": "TP53",
                "HGVSc": "ENST00000269305:c.743G>A",
                "HGVSp": "ENSP00000269305:p.Arg248Gln",
                "Consequence": "missense_variant",
                "EXON": "7/11",
            }
        },
    }
    doc = _latest_doc("variants_collection", prefer_dev_rna_wgs=prefer_dev_rna_wgs)
    return _with_defaults(doc, defaults)


def cnv_doc() -> dict:
    """Handle cnv doc.

    Returns:
        dict: The function result.
    """
    defaults = {
        "_id": "cnv1",
        "SAMPLE_ID": "s1",
        "gene": "ERBB2",
        "cnv_type": "gain",
        "interesting": True,
    }
    doc = _latest_doc("cnvs_collection")
    return _with_defaults(doc, defaults)


def fusion_doc(*, prefer_dev_rna_wgs: bool = True) -> dict:
    """Handle fusion doc.

    Args:
        prefer_dev_rna_wgs (bool): Value for ``prefer_dev_rna_wgs``.

    Returns:
        dict: The function result.
    """
    defaults = {
        "_id": "fus1",
        "SAMPLE_ID": "s1",
        "gene1": "EML4",
        "gene2": "ALK",
        "genes": "EML4^ALK",
        "interesting": True,
        "calls": [
            {"selected": 1, "breakpoint1": "2:42522694", "breakpoint2": "2:29443657"}
        ],
        "classification": {"class": 2},
    }
    doc = _latest_doc("fusions_collection", prefer_dev_rna_wgs=prefer_dev_rna_wgs)
    return _with_defaults(doc, defaults)


def reported_variant_doc() -> dict:
    """Handle reported variant doc.

    Returns:
        dict: The function result.
    """
    defaults = {
        "_id": "rv1",
        "sample_oid": "s1",
        "sample_name": "SAMPLE_001",
        "report_oid": "r1",
        "report_id": "RID1",
        "annotation_oid": "ann1",
        "annotation_text_oid": "anntxt1",
        "gene": "TP53",
        "simple_id": "17_7579472_C_T",
        "simple_id_hash": "hash_17_7579472_C_T",
        "tier": 2,
    }
    doc = _latest_doc("reported_variants_collection")
    return _with_defaults(doc, defaults)


def role_doc() -> dict:
    """Handle role doc.

    Returns:
        dict: The function result.
    """
    defaults = {
        "_id": "admin",
        "role_id": "admin",
        "label": "Administrator",
        "permissions": ["view_role", "create_role"],
        "deny_permissions": [],
        "level": 99999,
    }
    doc = _latest_doc("roles_collection")
    return _with_defaults(doc, defaults)


def permission_doc() -> dict:
    """Handle permission doc.

    Returns:
        dict: The function result.
    """
    defaults = {
        "_id": "view_role",
        "permission_id": "view_role",
        "label": "View Role",
        "category": "RBAC",
        "is_active": True,
    }
    doc = _latest_doc("permissions_collection")
    return _with_defaults(doc, defaults)


def schema_doc() -> dict:
    """Handle schema doc.

    Returns:
        dict: The function result.
    """
    defaults = {
        "_id": "rbac_role_schema_v1",
        "schema_id": "rbac_role_schema_v1",
        "schema_type": "rbac_role",
        "schema_category": "RBAC_role",
        "version": 1,
        "fields": {
            "permissions": {"options": [], "default": []},
            "deny_permissions": {"options": [], "default": []},
            "created_by": {"default": None},
            "created_on": {"default": None},
            "updated_by": {"default": None},
            "updated_on": {"default": None},
        },
    }
    doc = _latest_doc("schemas_collection")
    return _with_defaults(doc, defaults)


def isgl_doc() -> dict:
    """Handle isgl doc.

    Returns:
        dict: The function result.
    """
    defaults = {
        "_id": "gl1",
        "displayname": "Myeloid shortlist",
        "version": 1,
        "adhoc": False,
        "gene_count": 2,
        "genes": ["TP53", "NPM1"],
        "assays": ["WGS"],
        "is_active": True,
    }
    doc = _latest_doc("insilico_genelist_collection")
    return _with_defaults(doc, defaults)
