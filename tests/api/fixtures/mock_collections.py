"""Collection-shaped mock documents for API route tests.

These fixtures intentionally mirror key fields used in API routes and services.
"""

from __future__ import annotations

from copy import deepcopy

from api.app import ApiUser


def user_doc() -> dict:
    return {
        "_id": "u1",
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


def api_user() -> ApiUser:
    doc = user_doc()
    return ApiUser(
        id=str(doc["_id"]),
        email=doc["email"],
        fullname=doc["fullname"],
        username=doc["username"],
        role=doc["role"],
        access_level=int(doc["access_level"]),
        permissions=list(doc["permissions"]),
        denied_permissions=list(doc["deny_permissions"]),
        assays=list(doc["assays"]),
        assay_groups=list(doc["assay_groups"]),
        envs=list(doc["envs"]),
        asp_map=deepcopy(doc["asp_map"]),
    )


def sample_doc() -> dict:
    return {
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


def assay_config_doc() -> dict:
    return {
        "_id": "aspc1",
        "schema_name": "aspc_schema_v1",
        "asp_group": "dna",
        "analysis_types": ["SNV", "CNV", "BIOMARKER"],
        "filters": deepcopy(sample_doc()["filters"]),
        "reporting": {
            "report_path": "dna_report.html",
            "plots_path": "reports/plots",
        },
        "verification_samples": {"SAMPLE": ["1:1:A:T"]},
    }


def variant_doc() -> dict:
    return {
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


def cnv_doc() -> dict:
    return {
        "_id": "cnv1",
        "SAMPLE_ID": "s1",
        "gene": "ERBB2",
        "cnv_type": "gain",
        "interesting": True,
    }


def fusion_doc() -> dict:
    return {
        "_id": "fus1",
        "SAMPLE_ID": "s1",
        "gene1": "EML4",
        "gene2": "ALK",
        "genes": "EML4^ALK",
        "interesting": True,
        "calls": [
            {
                "selected": 1,
                "breakpoint1": "2:42522694",
                "breakpoint2": "2:29443657",
            }
        ],
        "classification": {"class": 2},
    }


def reported_variant_doc() -> dict:
    return {
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


def role_doc() -> dict:
    return {
        "_id": "admin",
        "label": "Administrator",
        "permissions": ["view_role", "create_role"],
        "deny_permissions": [],
        "level": 99999,
    }


def permission_doc() -> dict:
    return {
        "_id": "view_role",
        "label": "View Role",
        "category": "RBAC",
        "is_active": True,
    }


def schema_doc() -> dict:
    return {
        "_id": "rbac_role_schema_v1",
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


def isgl_doc() -> dict:
    return {
        "_id": "gl1",
        "displayname": "Myeloid shortlist",
        "version": 1,
        "adhoc": False,
        "gene_count": 2,
        "genes": ["TP53", "NPM1"],
        "assays": ["WGS"],
        "is_active": True,
    }
