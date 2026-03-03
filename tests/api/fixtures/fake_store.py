"""Fake store/handler harness for integration-style API route tests."""

from __future__ import annotations

from dataclasses import dataclass, field
from types import SimpleNamespace
from typing import Any

from tests.api.fixtures import mock_collections as fx


@dataclass
class FakeHandler:
    """Generic fake handler that can expose arbitrary methods."""

    methods: dict[str, Any] = field(default_factory=dict)

    def __getattr__(self, name: str) -> Any:
        if name not in self.methods:
            raise AttributeError(name)
        return self.methods[name]


def build_fake_store() -> SimpleNamespace:
    """Build a fake store namespace with collection-shaped defaults."""

    sample = fx.sample_doc()
    role = fx.role_doc()
    schema = fx.schema_doc()
    isgl = fx.isgl_doc()
    variant = fx.variant_doc()
    fusion = fx.fusion_doc()

    return SimpleNamespace(
        sample_handler=FakeHandler(
            {
                "get_sample": lambda sample_id: sample,
                "get_sample_by_id": lambda sample_id: sample,
                "hidden_sample_comments": lambda oid: False,
                "update_sample_filters": lambda sample_id, filters: None,
                "get_samples": lambda **kwargs: [sample],
            }
        ),
        asp_handler=FakeHandler(
            {
                "get_asp": lambda asp_name: {"_id": "asp1", "asp_group": "dna", "covered_genes": ["TP53"]},
                "get_asp_genes": lambda asp_name: (["TP53", "NPM1"], ["BRCA1"]),
                "get_all_asps": lambda: [{"_id": "asp1", "asp_group": "dna"}],
            }
        ),
        isgl_handler=FakeHandler(
            {
                "get_isgl": lambda _id, **kwargs: isgl,
                "get_isgl_by_ids": lambda ids: {isgl["_id"]: isgl},
                "get_isgl_by_asp": lambda asp_name=None, assay=None, **kwargs: [isgl],
            }
        ),
        roles_handler=FakeHandler(
            {
                "get_all_roles": lambda: [role],
                "get_role": lambda role_id: role if role_id == role["_id"] else None,
            }
        ),
        schema_handler=FakeHandler(
            {
                "get_schemas_by_category_type": lambda **kwargs: [schema],
                "get_schema": lambda name: schema,
            }
        ),
        permissions_handler=FakeHandler(
            {
                "get_all_permissions": lambda **kwargs: [fx.permission_doc()],
                "get": lambda perm_id: fx.permission_doc(),
            }
        ),
        variant_handler=FakeHandler(
            {
                "get_variant": lambda var_id: variant,
                "get_case_variants": lambda query: [variant],
                "get_variant_stats": lambda sample_id, genes=None: {"total": 1},
                "hidden_var_comments": lambda var_id: False,
                "get_variant_in_other_samples": lambda var: [],
            }
        ),
        fusion_handler=FakeHandler(
            {
                "get_fusion": lambda fusion_id: fusion,
                "get_sample_fusions": lambda query: [fusion],
                "mark_false_positive_fusion": lambda fusion_id: None,
                "unmark_false_positive_fusion": lambda fusion_id: None,
                "pick_fusion": lambda fusion_id, callidx, num_calls: None,
                "hide_fus_comment": lambda fusion_id, comment_id: None,
                "unhide_fus_comment": lambda fusion_id, comment_id: None,
                "mark_false_positive_bulk": lambda ids, apply: None,
                "mark_irrelevant_bulk": lambda ids, apply: None,
            }
        ),
        cnv_handler=FakeHandler({"get_sample_cnvs": lambda query: [fx.cnv_doc()]}),
        biomarker_handler=FakeHandler({"get_sample_biomarkers": lambda sample_id: [{"_id": "b1", "name": "TMB"}]}),
        transloc_handler=FakeHandler({"get_sample_translocations": lambda sample_id: []}),
        blacklist_handler=FakeHandler({"add_blacklist_data": lambda variants, assay_group: variants}),
        annotation_handler=FakeHandler(
            {
                "get_global_annotations": lambda variant, assay_group, subpanel: ([], {"class": 2}, [], []),
                "find_variants_by_search_string": lambda **kwargs: [],
                "get_tier_stats_by_search": lambda **kwargs: {"total": {}, "by_assay": {}},
                "get_annotation_text_by_oid": lambda oid: {"_id": oid, "text": "note"},
            }
        ),
        reported_variants_handler=FakeHandler({"list_reported_variants": lambda query: [fx.reported_variant_doc()]}),
        hgnc_handler=FakeHandler(
            {
                "get_metadata_by_symbol": lambda symbol: {"symbol": symbol},
                "get_metadata_by_hgnc_id": lambda hgnc_id: {"hgnc_id": hgnc_id},
                "get_metadata_by_symbols": lambda symbols: [{"symbol": s} for s in symbols],
            }
        ),
        vep_meta_handler=FakeHandler(
            {
                "get_variant_class_translations": lambda vep: {},
                "get_conseq_translations": lambda vep: {},
            }
        ),
        bam_service_handler=FakeHandler({"get_bams": lambda sample_ids: []}),
        oncokb_handler=FakeHandler({"get_oncokb_action_gene": lambda symbol: {"Hugo Symbol": symbol}}),
        expression_handler=FakeHandler({"get_expression_data": lambda tx: []}),
        rna_expression_handler=FakeHandler({"get_rna_expression": lambda sid: {}}),
        rna_classification_handler=FakeHandler({"get_rna_classification": lambda sid: {}}),
        rna_qc_handler=FakeHandler({"get_rna_qc": lambda sid: {}}),
    )
