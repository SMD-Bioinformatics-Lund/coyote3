"""DNA repository facade used by routers and services."""

from __future__ import annotations

from api.extensions import store


class DnaRouteRepository:
    """Repository facade for DNA routes with dynamic handler resolution."""

    @property
    def cnv_handler(self):
        return store.cnv_handler

    @property
    def asp_handler(self):
        return store.asp_handler

    @property
    def isgl_handler(self):
        return store.isgl_handler

    @property
    def variant_handler(self):
        return store.variant_handler

    @property
    def blacklist_handler(self):
        return store.blacklist_handler

    @property
    def bam_service_handler(self):
        return store.bam_service_handler

    @property
    def vep_meta_handler(self):
        return store.vep_meta_handler

    @property
    def sample_handler(self):
        return store.sample_handler

    @property
    def schema_handler(self):
        return store.schema_handler

    @property
    def oncokb_handler(self):
        return store.oncokb_handler

    @property
    def biomarker_handler(self):
        return store.biomarker_handler

    @property
    def transloc_handler(self):
        return store.transloc_handler

    @property
    def annotation_handler(self):
        return store.annotation_handler

    @property
    def expression_handler(self):
        return store.expression_handler

    @property
    def civic_handler(self):
        return store.civic_handler

    @property
    def brca_handler(self):
        return store.brca_handler

    @property
    def iarc_tp53_handler(self):
        return store.iarc_tp53_handler

    @property
    def fusion_handler(self):
        return store.fusion_handler


__all__ = ["DnaRouteRepository"]
