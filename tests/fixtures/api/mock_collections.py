"""Deterministic collection-shaped documents for API tests."""

from __future__ import annotations

from copy import deepcopy

from api.security.access import ApiUser


def user_doc() -> dict:
    """User doc.

    Returns:
        dict: The function result.
    """
    defaults = {
        "_id": "u1",
        "email": "tester@example.com",
        "fullname": "Test User",
        "username": "tester",
        "roles": ["admin", "superuser"],
        "role": "admin",
        "access_level": 99999,
        "asp_ids": ["wgs", "rna_panel"],
        "asp_groups": ["dna", "rna"],
        "envs": ["production"],
        "asp_map": {"DNA": {"PANEL": {"dna": ["wgs"]}}},
    }
    # users are sourced through roles/users collections; keep stable defaults.
    return defaults


def api_user() -> ApiUser:
    """Api user.

    Returns:
        ApiUser: The function result.
    """
    doc = user_doc()
    return ApiUser(
        id=str(doc.get("_id") or "u1"),
        email=str(doc.get("email") or "tester@example.com"),
        fullname=str(doc.get("fullname") or "Test User"),
        username=str(doc.get("username") or "tester"),
        roles=list(doc.get("roles") or [str(doc.get("role") or "admin")]),
        role=str(doc.get("role") or "admin"),
        access_level=int(doc.get("access_level") or 99),
        permissions=list(
            doc.get("permissions")
            or ["report:preview", "report:create", "role:view", "sample:edit:own"]
        ),
        asp_ids=list(doc.get("asp_ids") or []),
        asp_groups=list(doc.get("asp_groups") or []),
        envs=list(doc.get("envs") or []),
        asp_map=deepcopy(doc.get("asp_map") or {}),
        auth_type=list(doc.get("auth_type") or ["local"]),
    )


def sample_doc() -> dict:
    """Sample doc.

    Returns:
        dict: The function result.
    """
    defaults = {
        "_id": "s1",
        "name": "SAMPLE_001",
        "asp_id": "wgs",
        "environment": "production",
        "sequencing_scope": "panel",
        "omics_layer": "dna",
        "case_id": "CASE001",
        "control_id": "CTRL001",
        "subpanel_id": "myeloid",
        "database_versions": {"vep": "110"},
        "report_num": 2,
        "reports": [{"_id": "r1", "report_id": "RID1", "report_num": 1, "time_created": 1}],
        "case": {"clarity_id": "CLARITY_CASE_001"},
        "control": {"clarity_id": "CLARITY_CTRL_001"},
        "analysis_intents": ["somatic"],
        "filters": {
            "somatic": {
                "snv": {
                    "max_freq": 1.0,
                    "min_freq": 0.05,
                    "max_control_freq": 0.2,
                    "min_depth": 100,
                    "min_alt_reads": 5,
                    "max_popfreq": 0.01,
                    "vep_consequences": ["missense_variant"],
                    "snvlists": ["gl1"],
                    "adhoc_genes": {"label": "focus", "genes": ["TP53", "NPM1"]},
                },
                "cnv": {"cnvlists": ["gl1"]},
            }
        },
    }
    return defaults


def assay_config_doc() -> dict:
    """Assay config doc.

    Returns:
        dict: The function result.
    """
    defaults = {
        "_id": "aspc1",
        "asp_group": "dna",
        "analysis_types": ["SNV", "CNV", "BIOMARKER"],
        "filters": deepcopy(sample_doc().get("filters", {})),
        "reporting": {"report_path": "dna_report.html", "plots_path": "reports/plots"},
        "verification_samples": {"SAMPLE": ["1:1:A:T"]},
    }
    return defaults


def variant_doc() -> dict:
    """Variant doc.

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
        "simple_id_hash": "862b46287a08e369aa99f8f3777f44b9",
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
    return defaults


def cnv_doc() -> dict:
    """Cnv doc.

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
    return defaults


def fusion_doc() -> dict:
    """Fusion doc.

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
        "calls": [{"selected": 1, "breakpoint1": "2:42522694", "breakpoint2": "2:29443657"}],
        "classification": {"class": 2},
    }
    return defaults


def reported_variant_doc() -> dict:
    """Reported variant doc.

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
        "simple_id_hash": "862b46287a08e369aa99f8f3777f44b9",
        "tier": 2,
    }
    return defaults


def role_doc() -> dict:
    """Role doc.

    Returns:
        dict: The function result.
    """
    defaults = {
        "_id": "admin",
        "role_id": "admin",
        "label": "Administrator",
        "permissions": ["role:view", "role:create"],
        "level": 99999,
    }
    return defaults


def permission_doc() -> dict:
    """Permission doc.

    Returns:
        dict: The function result.
    """
    defaults = {
        "_id": "role:view",
        "permission_id": "role:view",
        "label": "View Role",
        "category": "RBAC",
        "is_active": True,
    }
    return defaults


def schema_doc() -> dict:
    """Schema doc.

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
            "created_by": {"default": None},
            "created_on": {"default": None},
            "updated_by": {"default": None},
            "updated_on": {"default": None},
        },
    }
    return defaults


def isgl_doc() -> dict:
    """Isgl doc.

    Returns:
        dict: The function result.
    """
    defaults = {
        "_id": "gl1",
        "isgl_id": "gl1",
        "displayname": "Myeloid shortlist",
        "version": 1,
        "adhoc": False,
        "gene_count": 2,
        "genes": ["TP53", "NPM1"],
        "assays": ["WGS"],
        "list_type": ["snv", "cnv", "fusion"],
        "is_active": True,
    }
    return defaults
