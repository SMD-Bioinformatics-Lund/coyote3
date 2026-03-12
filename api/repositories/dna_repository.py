"""DNA repository facade used by routers and services."""

from __future__ import annotations

from api.extensions import store


class DnaRouteRepository:
    """Repository facade for DNA routes with dynamic handler resolution."""

    @property
    def cnv_handler(self):
        """Handle cnv handler.

        Returns:
            The function result.
        """
        return store.cnv_handler

    @property
    def asp_handler(self):
        """Handle asp handler.

        Returns:
            The function result.
        """
        return store.asp_handler

    @property
    def isgl_handler(self):
        """Handle isgl handler.

        Returns:
            The function result.
        """
        return store.isgl_handler

    @property
    def variant_handler(self):
        """Handle variant handler.

        Returns:
            The function result.
        """
        return store.variant_handler

    @property
    def blacklist_handler(self):
        """Handle blacklist handler.

        Returns:
            The function result.
        """
        return store.blacklist_handler

    @property
    def bam_service_handler(self):
        """Handle bam service handler.

        Returns:
            The function result.
        """
        return store.bam_service_handler

    @property
    def vep_meta_handler(self):
        """Handle vep meta handler.

        Returns:
            The function result.
        """
        return store.vep_meta_handler

    @property
    def sample_handler(self):
        """Handle sample handler.

        Returns:
            The function result.
        """
        return store.sample_handler

    @property
    def schema_handler(self):
        """Handle schema handler.

        Returns:
            The function result.
        """
        return store.schema_handler

    @property
    def oncokb_handler(self):
        """Handle oncokb handler.

        Returns:
            The function result.
        """
        return store.oncokb_handler

    @property
    def biomarker_handler(self):
        """Handle biomarker handler.

        Returns:
            The function result.
        """
        return store.biomarker_handler

    @property
    def transloc_handler(self):
        """Handle transloc handler.

        Returns:
            The function result.
        """
        return store.transloc_handler

    @property
    def annotation_handler(self):
        """Handle annotation handler.

        Returns:
            The function result.
        """
        return store.annotation_handler

    @property
    def expression_handler(self):
        """Handle expression handler.

        Returns:
            The function result.
        """
        return store.expression_handler

    @property
    def civic_handler(self):
        """Handle civic handler.

        Returns:
            The function result.
        """
        return store.civic_handler

    @property
    def brca_handler(self):
        """Handle brca handler.

        Returns:
            The function result.
        """
        return store.brca_handler

    @property
    def iarc_tp53_handler(self):
        """Handle iarc tp53 handler.

        Returns:
            The function result.
        """
        return store.iarc_tp53_handler

    @property
    def fusion_handler(self):
        """Handle fusion handler.

        Returns:
            The function result.
        """
        return store.fusion_handler


__all__ = ["DnaRouteRepository"]
