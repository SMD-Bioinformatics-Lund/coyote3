"""Mongo-backed repository for DNA route data access."""

from __future__ import annotations

from api.extensions import store


class MongoDNARouteRepository:
    """Provide mongo dna route persistence operations.
    """
    def __init__(self) -> None:
        """Handle __init__.
        """
        self.cnv_handler = store.cnv_handler
        self.asp_handler = store.asp_handler
        self.isgl_handler = store.isgl_handler
        self.variant_handler = store.variant_handler
        self.blacklist_handler = store.blacklist_handler
        self.bam_service_handler = store.bam_service_handler
        self.vep_meta_handler = store.vep_meta_handler
        self.sample_handler = store.sample_handler
        self.schema_handler = store.schema_handler
        self.oncokb_handler = store.oncokb_handler
        self.biomarker_handler = store.biomarker_handler
        self.transloc_handler = store.transloc_handler
        self.annotation_handler = store.annotation_handler
        self.expression_handler = store.expression_handler
        self.civic_handler = store.civic_handler
        self.brca_handler = store.brca_handler
        self.iarc_tp53_handler = store.iarc_tp53_handler
        self.fusion_handler = store.fusion_handler
