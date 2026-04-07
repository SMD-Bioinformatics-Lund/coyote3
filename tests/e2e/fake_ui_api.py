"""Stateful API stubs for Playwright-driven Flask UI tests."""

from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any

from coyote.services.api_client import endpoints as api_endpoints
from coyote.services.api_client.base import ApiPayload, ApiRequestError
from tests.fixtures.api import mock_collections as fx

REPO_ROOT = Path(__file__).resolve().parents[2]
PLOT_FIXTURE_DIR = REPO_ROOT / "tests" / "data" / "ingest_demo"


def _as_payload(value: Any) -> Any:
    """Recursively convert dictionaries to ApiPayload objects."""
    if isinstance(value, dict):
        return ApiPayload({key: _as_payload(item) for key, item in value.items()})
    if isinstance(value, list):
        return [_as_payload(item) for item in value]
    return value


class E2EApiState:
    """Hold mutable API fixture state for browser-driven UI tests."""

    def __init__(self) -> None:
        self.reset()

    def reset(self) -> None:
        """Reset the fake API to a deterministic default state."""
        self.user = deepcopy(fx.user_doc())
        self.user.update(
            {
                "_id": "admin-1",
                "user_id": "admin-1",
                "username": "admin",
                "email": "admin@example.com",
                "fullname": "Admin User",
                "role": "admin",
                "access_level": 99999,
                "permissions": [
                    "preview_report",
                    "create_report",
                    "edit_sample",
                    "view_sample_global",
                    "view_igv",
                    "manage_snvs",
                    "manage_cnvs",
                    "assign_tier",
                ],
                "deny_permissions": [],
                "denied_permissions": [],
                "auth_type": "coyote3",
                "must_change_password": False,
                "assay_groups": ["dna", "rna"],
                "assays": ["WGS", "RNA_PANEL"],
                "asp_map": {"DNA": {"WGS": {"dna": ["WGS"]}}},
            }
        )

        self.sample = deepcopy(fx.sample_doc())
        self.sample.update(
            {
                "name": "SAMPLE_001",
                "omics_layer": "dna",
                "profile": "production",
                "assay": "WGS",
                "subpanel": "myeloid",
                "cov": True,
                "comments": [],
                "time_added": "2026-04-01T08:00:00+00:00",
                "purity": 0.72,
                "cnvprofile": str(PLOT_FIXTURE_DIR / "generic_case_control.modeled.png"),
                "filters": {
                    "max_freq": 1.0,
                    "min_freq": 0.05,
                    "max_control_freq": 0.2,
                    "min_depth": 100,
                    "min_alt_reads": 5,
                    "max_popfreq": 0.01,
                    "vep_consequences": ["missense_variant"],
                    "genelists": ["GL-DEMO"],
                    "adhoc_genes": {"label": "focus", "genes": ["TP53", "NPM1"]},
                },
            }
        )

        self.assay_config = deepcopy(fx.assay_config_doc())
        self.assay_config.update(
            {
                "asp_group": "dna",
                "analysis_types": ["SNV", "CNV", "BIOMARKER"],
                "reporting": {
                    "report_path": "dna_report.html",
                    "plots_path": "reports/plots",
                },
            }
        )

        self.genelist = deepcopy(fx.isgl_doc())
        self.genelist.update(
            {
                "_id": "gl1",
                "isgl_id": "gl1",
            }
        )

        self.variant = deepcopy(fx.variant_doc())
        self.variant.update(
            {
                "_id": "v1",
                "variant_class": "SNV",
                "classification": {
                    "class": 999,
                    "transcript": "ENST00000269305",
                },
                "additional_classification": None,
                "other_classification": [],
                "blacklist": True,
                "override_blacklist": False,
                "interesting": True,
                "fp": False,
                "irrelevant": False,
                "comments": [],
                "SAMPLE_ID": "s1",
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
        )

        self.cnv = deepcopy(fx.cnv_doc())
        self.cnv.update(
            {
                "_id": "cnv1",
                "SAMPLE_ID": "s1",
                "chr": "17",
                "start": 37844167,
                "end": 37884910,
                "ratio": 1.2,
                "size": 40743,
                "callers": ["cnvkit"],
                "genes": [{"gene": "ERBB2", "class": True}],
                "PR": 12,
                "fp": False,
                "interesting": True,
                "noteworthy": False,
                "comments": [],
            }
        )

        self.translocation = {
            "_id": "tl1",
            "SAMPLE_ID": self.sample["name"],
            "gene1": "BCR",
            "gene2": "ABL1",
            "interesting": True,
        }

        self.sample_ids = {"case": "s1", "control": "ctrl1"}
        self.bam_id: dict[str, list[str]] = {
            "s1": ["demo_runs/SAMPLE_001.case.bam"],
            "ctrl1": ["demo_runs/SAMPLE_001.control.bam"],
        }
        self.session_token = "e2e-session-token"

    def get_json(self, path: str, *, params: dict[str, Any] | None = None) -> ApiPayload:
        """Return a fixture-shaped GET payload."""
        if path == api_endpoints.internal("roles", "levels"):
            return _as_payload(
                {
                    "role_levels": {
                        "viewer": 1,
                        "user": 9,
                        "manager": 99,
                        "developer": 9999,
                        "admin": 99999,
                    }
                }
            )

        if path == api_endpoints.auth("session"):
            return _as_payload({"user": deepcopy(self.user)})

        if path == api_endpoints.dashboard("summary"):
            return _as_payload(
                {
                    "total_samples": 1,
                    "analysed_samples": 1,
                    "pending_samples": 0,
                    "user_samples_stats": {"admin": 1},
                    "variant_stats": {"snv": 1, "cnv": 1},
                    "unique_gene_count_all_panels": 3,
                    "assay_gene_stats_grouped": {"dna": {"WGS": 3}},
                    "sample_stats": {"production": 1},
                }
            )

        if path == api_endpoints.home("samples"):
            return _as_payload(
                {
                    "live_samples": [deepcopy(self.sample)],
                    "done_samples": [],
                    "sample_view": "live",
                    "profile_scope": "production",
                    "page": 1,
                    "per_page": 30,
                    "live_page": 1,
                    "live_per_page": 30,
                    "done_page": 1,
                    "done_per_page": 30,
                    "has_next_live": False,
                    "has_next_done": False,
                }
            )

        if path == api_endpoints.home_sample(self.sample["name"], "edit_context"):
            return _as_payload(
                {
                    "sample": deepcopy(self.sample),
                    "asp": deepcopy(self.assay_config),
                    "assay_groups": ["dna", "rna"],
                    "panel_types": ["dna"],
                    "panel_techs": ["wgs"],
                    "profile_choices": ["production"],
                    "variant_stats_raw": {"snv": 1, "cnv": 1},
                    "variant_stats_filtered": {"snv": 1, "cnv": 1},
                }
            )

        if path == api_endpoints.home_sample(self.sample["name"], "isgls"):
            return _as_payload({"items": [deepcopy(self.genelist)]})

        if path == api_endpoints.home_sample(self.sample["name"], "effective_genes", "all"):
            return _as_payload({"items": ["TP53", "NPM1"], "asp_covered_genes_count": 2})

        if path == api_endpoints.dna_sample(self.sample["name"], "small_variants"):
            return _as_payload(
                {
                    "sample": deepcopy(self.sample),
                    "filters": deepcopy(self.sample["filters"]),
                    "assay_config": deepcopy(self.assay_config),
                    "sample_ids": deepcopy(self.sample_ids),
                    "assay_group": "dna",
                    "analysis_sections": ["SNV", "CNV", "BIOMARKER"],
                    "display_sections_data": {
                        "snvs": [deepcopy(self.variant)],
                        "cnvs": [deepcopy(self.cnv)],
                        "biomarkers": [{"_id": "bio1", "name": "TMB", "value": "High"}],
                    },
                    "ai_text": "E2E summary",
                    "assay_panels": [deepcopy(self.genelist)],
                    "all_panel_genelist_names": ["gl1"],
                    "checked_genelists": ["gl1"],
                    "checked_genelists_dict": {
                        "gl1": {
                            "is_active": True,
                            "adhoc": False,
                            "covered": ["NPM1", "TP53"],
                            "genes": ["NPM1", "TP53"],
                            "uncovered": [],
                        }
                    },
                    "verification_sample_used": None,
                    "hidden_comments": False,
                    "vep_var_class_translations": {},
                    "vep_conseq_translations": {},
                    "bam_id": deepcopy(self.bam_id),
                    "oncokb_genes": ["TP53"],
                }
            )

        if path == api_endpoints.dna_sample(
            self.sample["name"], "small_variants", self.variant["_id"]
        ):
            return _as_payload(
                {
                    "variant": deepcopy(self.variant),
                    "in_other": [],
                    "annotations": [],
                    "hidden_comments": False,
                    "latest_classification": {"class": 2},
                    "expression": {},
                    "civic": None,
                    "civic_gene": None,
                    "oncokb": None,
                    "oncokb_action": [],
                    "oncokb_gene": None,
                    "sample": deepcopy(self.sample),
                    "brca_exchange": None,
                    "iarc_tp53": None,
                    "assay_group": "dna",
                    "pon": [],
                    "other_classifications": [],
                    "subpanel": self.sample.get("subpanel"),
                    "sample_ids": deepcopy(self.sample_ids),
                    "bam_id": deepcopy(self.bam_id),
                    "annotations_interesting": [],
                    "vep_var_class_translations": {},
                    "vep_conseq_translations": {},
                    "assay_group_mappings": {},
                }
            )

        if path == api_endpoints.dna_sample(self.sample["name"], "cnvs", self.cnv["_id"]):
            return _as_payload(
                {
                    "cnv": deepcopy(self.cnv),
                    "sample": deepcopy(self.sample),
                    "assay_group": "dna",
                    "annotations": [],
                    "sample_ids": deepcopy(self.sample_ids),
                    "bam_id": deepcopy(self.bam_id),
                    "hidden_comments": False,
                }
            )

        if path == api_endpoints.dna_sample(self.sample["name"], "translocations", "tl1"):
            return _as_payload(
                {
                    "translocation": deepcopy(self.translocation),
                    "sample": deepcopy(self.sample),
                    "assay_group": "dna",
                    "annotations": [],
                    "bam_id": deepcopy(self.bam_id),
                    "vep_conseq_translations": {},
                    "hidden_comments": False,
                }
            )

        if path == api_endpoints.coverage("samples", self.sample["name"]):
            cov_cutoff = int((params or {}).get("cov_cutoff", 500))
            return _as_payload(
                {
                    "coverage": [{"gene": "TP53", "mean_depth": 650}],
                    "cov_cutoff": cov_cutoff,
                    "sample": deepcopy(self.sample),
                    "genelists": ["GL-DEMO"],
                    "smp_grp": "dna",
                    "cov_table": {
                        "TP53": {
                            "EXON_7": {
                                "chr": "17",
                                "start": 7579200,
                                "end": 7579600,
                                "cov": 650,
                            }
                        }
                    },
                }
            )

        if path == api_endpoints.dna_sample(self.sample["name"], "reports", "preview"):
            return _as_payload(
                {
                    "report": {
                        "template": "report_preview.html",
                        "context": {
                            "sample_name": self.sample["name"],
                            "report_title": "DNA Preview Report",
                            "variant_count": 1,
                        },
                        "snapshot_rows": [],
                    }
                }
            )

        if path == api_endpoints.dna_sample(self.sample["name"], "plot_context"):
            return _as_payload(
                {
                    "sample": deepcopy(self.sample),
                    "assay_config": deepcopy(self.assay_config),
                    "plots_base_dir": str(PLOT_FIXTURE_DIR),
                }
            )

        raise ApiRequestError(f"Unhandled e2e GET path: {path}", status_code=404)

    def post_json(
        self,
        path: str,
        *,
        json_body: dict[str, Any] | None = None,
    ) -> ApiPayload:
        """Return a fixture-shaped POST payload."""
        if path == api_endpoints.auth("sessions"):
            username = str((json_body or {}).get("username") or "").strip().lower()
            password = str((json_body or {}).get("password") or "")
            if username != "admin@example.com" or password != "Coyote3.Admin":
                raise ApiRequestError("Invalid credentials.", status_code=401)
            return _as_payload({"user": deepcopy(self.user)})

        if path == api_endpoints.dna_sample(
            self.sample["name"], "small_variants", self.variant["_id"], "blacklist-entries"
        ):
            self.variant["blacklist"] = True
            self.variant["override_blacklist"] = False
            return _as_payload({"status": "ok"})

        if path == api_endpoints.coverage("blacklist", "entries"):
            return _as_payload({"message": "updated"})

        if path == api_endpoints.dna_sample(self.sample["name"], "reports"):
            return _as_payload({"report": {"id": "RID1", "file": "RID1.html"}})

        if path == api_endpoints.auth("password", "reset", "request"):
            return _as_payload({"status": "ok"})

        if path == api_endpoints.auth("password", "reset", "confirm"):
            return _as_payload({"status": "ok"})

        raise ApiRequestError(f"Unhandled e2e POST path: {path}", status_code=404)

    def patch_json(self, path: str) -> ApiPayload:
        """Return a fixture-shaped PATCH payload."""
        if path == api_endpoints.dna_sample(
            self.sample["name"],
            "small_variants",
            self.variant["_id"],
            "flags",
            "override-blacklist",
        ):
            self.variant["override_blacklist"] = True
            return _as_payload({"status": "ok"})

        raise ApiRequestError(f"Unhandled e2e PATCH path: {path}", status_code=404)

    def put_json(
        self,
        path: str,
        *,
        json_body: dict[str, Any] | None = None,
    ) -> ApiPayload:
        """Return a fixture-shaped PUT payload."""
        if path == api_endpoints.sample(self.sample["name"], "filters"):
            filters = deepcopy((json_body or {}).get("filters", {}))
            self.sample["filters"] = filters
            return _as_payload({"status": "ok", "filters": filters})

        raise ApiRequestError(f"Unhandled e2e PUT path: {path}", status_code=404)

    def delete_json(self, path: str) -> ApiPayload:
        """Return a fixture-shaped DELETE payload."""
        if path == api_endpoints.auth("sessions", "current"):
            return _as_payload({"status": "ok"})

        if path == api_endpoints.dna_sample(
            self.sample["name"],
            "small_variants",
            self.variant["_id"],
            "flags",
            "override-blacklist",
        ):
            self.variant["override_blacklist"] = False
            return _as_payload({"status": "ok"})

        raise ApiRequestError(f"Unhandled e2e DELETE path: {path}", status_code=404)
