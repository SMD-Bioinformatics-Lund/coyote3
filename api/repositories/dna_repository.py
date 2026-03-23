"""DNA repository facade used by routers and services."""

from __future__ import annotations

from api.extensions import store


class DnaRouteRepository:
    """Repository facade for DNA routes with dynamic handler resolution."""

    @property
    def cnv_handler(self):
        """Cnv handler.

        Returns:
            The function result.
        """
        return store.cnv_handler

    @property
    def asp_handler(self):
        """Asp handler.

        Returns:
            The function result.
        """
        return store.asp_handler

    @property
    def isgl_handler(self):
        """Isgl handler.

        Returns:
            The function result.
        """
        return store.isgl_handler

    @property
    def variant_handler(self):
        """Variant handler.

        Returns:
            The function result.
        """
        return store.variant_handler

    @property
    def blacklist_handler(self):
        """Blacklist handler.

        Returns:
            The function result.
        """
        return store.blacklist_handler

    @property
    def bam_service_handler(self):
        """Bam service handler.

        Returns:
            The function result.
        """
        return store.bam_service_handler

    @property
    def vep_meta_handler(self):
        """Vep meta handler.

        Returns:
            The function result.
        """
        return store.vep_meta_handler

    @property
    def sample_handler(self):
        """Sample handler.

        Returns:
            The function result.
        """
        return store.sample_handler

    @property
    def oncokb_handler(self):
        """Oncokb handler.

        Returns:
            The function result.
        """
        return store.oncokb_handler

    @property
    def biomarker_handler(self):
        """Biomarker handler.

        Returns:
            The function result.
        """
        return store.biomarker_handler

    @property
    def transloc_handler(self):
        """Transloc handler.

        Returns:
            The function result.
        """
        return store.transloc_handler

    @property
    def annotation_handler(self):
        """Annotation handler.

        Returns:
            The function result.
        """
        return store.annotation_handler

    @property
    def expression_handler(self):
        """Expression handler.

        Returns:
            The function result.
        """
        return store.expression_handler

    @property
    def civic_handler(self):
        """Civic handler.

        Returns:
            The function result.
        """
        return store.civic_handler

    @property
    def brca_handler(self):
        """Brca handler.

        Returns:
            The function result.
        """
        return store.brca_handler

    @property
    def iarc_tp53_handler(self):
        """Iarc tp53 handler.

        Returns:
            The function result.
        """
        return store.iarc_tp53_handler

    @property
    def fusion_handler(self):
        """Fusion handler.

        Returns:
            The function result.
        """
        return store.fusion_handler


__all__ = ["DnaRouteRepository"]
