"""Dna API client mixin methods."""

from __future__ import annotations

from typing import Any

from coyote.integrations.api.base import ApiPayload


class DnaApiClientMixin:
    def get_dna_variants(
        self, sample_id: str, headers: dict[str, str] | None = None
    ) -> ApiPayload:
        payload = self._get(f"/api/v1/dna/samples/{sample_id}/variants", headers=headers)
        return payload

    def get_dna_plot_context(
        self, sample_id: str, headers: dict[str, str] | None = None
    ) -> ApiPayload:
        payload = self._get(f"/api/v1/dna/samples/{sample_id}/plot_context", headers=headers)
        return payload

    def get_dna_variant(
        self, sample_id: str, var_id: str, headers: dict[str, str] | None = None
    ) -> ApiPayload:
        payload = self._get(
            f"/api/v1/dna/samples/{sample_id}/variants/{var_id}",
            headers=headers,
        )
        return payload

    def get_dna_cnv(
        self, sample_id: str, cnv_id: str, headers: dict[str, str] | None = None
    ) -> ApiPayload:
        payload = self._get(
            f"/api/v1/dna/samples/{sample_id}/cnvs/{cnv_id}",
            headers=headers,
        )
        return payload

    def get_dna_translocation(
        self, sample_id: str, transloc_id: str, headers: dict[str, str] | None = None
    ) -> ApiPayload:
        payload = self._get(
            f"/api/v1/dna/samples/{sample_id}/translocations/{transloc_id}",
            headers=headers,
        )
        return payload

    def get_dna_cnvs(
        self, sample_id: str, headers: dict[str, str] | None = None
    ) -> ApiPayload:
        payload = self._get(
            f"/api/v1/dna/samples/{sample_id}/cnvs",
            headers=headers,
        )
        return payload

    def get_dna_translocations(
        self, sample_id: str, headers: dict[str, str] | None = None
    ) -> ApiPayload:
        payload = self._get(
            f"/api/v1/dna/samples/{sample_id}/translocations",
            headers=headers,
        )
        return payload

    def get_dna_biomarkers(
        self, sample_id: str, headers: dict[str, str] | None = None
    ) -> ApiPayload:
        payload = self._get(
            f"/api/v1/dna/samples/{sample_id}/biomarkers",
            headers=headers,
        )
        return payload

    def get_dna_report_preview(
        self, sample_id: str, headers: dict[str, str] | None = None
    ) -> ApiPayload:
        payload = self._get(
            f"/api/v1/dna/samples/{sample_id}/report/preview",
            headers=headers,
        )
        return payload

    def save_dna_report(
        self, sample_id: str, headers: dict[str, str] | None = None
    ) -> ApiPayload:
        payload = self._post(
            f"/api/v1/dna/samples/{sample_id}/report/save",
            headers=headers,
        )
        return payload

    def mark_dna_cnv_interesting(
        self, sample_id: str, cnv_id: str, headers: dict[str, str] | None = None
    ) -> ApiPayload:
        payload = self._post(f"/api/v1/dna/samples/{sample_id}/cnvs/{cnv_id}/interesting", headers=headers)
        return payload

    def unmark_dna_cnv_interesting(
        self, sample_id: str, cnv_id: str, headers: dict[str, str] | None = None
    ) -> ApiPayload:
        payload = self._post(
            f"/api/v1/dna/samples/{sample_id}/cnvs/{cnv_id}/unmarkinteresting",
            headers=headers,
        )
        return payload

    def mark_dna_cnv_false_positive(
        self, sample_id: str, cnv_id: str, headers: dict[str, str] | None = None
    ) -> ApiPayload:
        payload = self._post(f"/api/v1/dna/samples/{sample_id}/cnvs/{cnv_id}/fpcnv", headers=headers)
        return payload

    def unmark_dna_cnv_false_positive(
        self, sample_id: str, cnv_id: str, headers: dict[str, str] | None = None
    ) -> ApiPayload:
        payload = self._post(f"/api/v1/dna/samples/{sample_id}/cnvs/{cnv_id}/unfpcnv", headers=headers)
        return payload

    def mark_dna_cnv_noteworthy(
        self, sample_id: str, cnv_id: str, headers: dict[str, str] | None = None
    ) -> ApiPayload:
        payload = self._post(
            f"/api/v1/dna/samples/{sample_id}/cnvs/{cnv_id}/noteworthycnv",
            headers=headers,
        )
        return payload

    def unmark_dna_cnv_noteworthy(
        self, sample_id: str, cnv_id: str, headers: dict[str, str] | None = None
    ) -> ApiPayload:
        payload = self._post(
            f"/api/v1/dna/samples/{sample_id}/cnvs/{cnv_id}/notnoteworthycnv",
            headers=headers,
        )
        return payload

    def hide_dna_cnv_comment(
        self, sample_id: str, cnv_id: str, comment_id: str, headers: dict[str, str] | None = None
    ) -> ApiPayload:
        payload = self._post(
            f"/api/v1/dna/samples/{sample_id}/cnvs/{cnv_id}/comments/{comment_id}/hide",
            headers=headers,
        )
        return payload

    def unhide_dna_cnv_comment(
        self, sample_id: str, cnv_id: str, comment_id: str, headers: dict[str, str] | None = None
    ) -> ApiPayload:
        payload = self._post(
            f"/api/v1/dna/samples/{sample_id}/cnvs/{cnv_id}/comments/{comment_id}/unhide",
            headers=headers,
        )
        return payload

    def mark_dna_translocation_interesting(
        self, sample_id: str, transloc_id: str, headers: dict[str, str] | None = None
    ) -> ApiPayload:
        payload = self._post(
            f"/api/v1/dna/samples/{sample_id}/translocations/{transloc_id}/interestingtransloc",
            headers=headers,
        )
        return payload

    def unmark_dna_translocation_interesting(
        self, sample_id: str, transloc_id: str, headers: dict[str, str] | None = None
    ) -> ApiPayload:
        payload = self._post(
            f"/api/v1/dna/samples/{sample_id}/translocations/{transloc_id}/uninterestingtransloc",
            headers=headers,
        )
        return payload

    def mark_dna_translocation_false_positive(
        self, sample_id: str, transloc_id: str, headers: dict[str, str] | None = None
    ) -> ApiPayload:
        payload = self._post(
            f"/api/v1/dna/samples/{sample_id}/translocations/{transloc_id}/fptransloc",
            headers=headers,
        )
        return payload

    def unmark_dna_translocation_false_positive(
        self, sample_id: str, transloc_id: str, headers: dict[str, str] | None = None
    ) -> ApiPayload:
        payload = self._post(
            f"/api/v1/dna/samples/{sample_id}/translocations/{transloc_id}/ptransloc",
            headers=headers,
        )
        return payload

    def hide_dna_translocation_comment(
        self, sample_id: str, transloc_id: str, comment_id: str, headers: dict[str, str] | None = None
    ) -> ApiPayload:
        payload = self._post(
            f"/api/v1/dna/samples/{sample_id}/translocations/{transloc_id}/comments/{comment_id}/hide",
            headers=headers,
        )
        return payload

    def unhide_dna_translocation_comment(
        self, sample_id: str, transloc_id: str, comment_id: str, headers: dict[str, str] | None = None
    ) -> ApiPayload:
        payload = self._post(
            f"/api/v1/dna/samples/{sample_id}/translocations/{transloc_id}/comments/{comment_id}/unhide",
            headers=headers,
        )
        return payload

    def mark_dna_variant_false_positive(
        self, sample_id: str, var_id: str, headers: dict[str, str] | None = None
    ) -> ApiPayload:
        payload = self._post(f"/api/v1/dna/samples/{sample_id}/variants/{var_id}/fp", headers=headers)
        return payload

    def unmark_dna_variant_false_positive(
        self, sample_id: str, var_id: str, headers: dict[str, str] | None = None
    ) -> ApiPayload:
        payload = self._post(f"/api/v1/dna/samples/{sample_id}/variants/{var_id}/unfp", headers=headers)
        return payload

    def mark_dna_variant_interesting(
        self, sample_id: str, var_id: str, headers: dict[str, str] | None = None
    ) -> ApiPayload:
        payload = self._post(f"/api/v1/dna/samples/{sample_id}/variants/{var_id}/interest", headers=headers)
        return payload

    def unmark_dna_variant_interesting(
        self, sample_id: str, var_id: str, headers: dict[str, str] | None = None
    ) -> ApiPayload:
        payload = self._post(
            f"/api/v1/dna/samples/{sample_id}/variants/{var_id}/uninterest",
            headers=headers,
        )
        return payload

    def mark_dna_variant_irrelevant(
        self, sample_id: str, var_id: str, headers: dict[str, str] | None = None
    ) -> ApiPayload:
        payload = self._post(
            f"/api/v1/dna/samples/{sample_id}/variants/{var_id}/irrelevant",
            headers=headers,
        )
        return payload

    def unmark_dna_variant_irrelevant(
        self, sample_id: str, var_id: str, headers: dict[str, str] | None = None
    ) -> ApiPayload:
        payload = self._post(
            f"/api/v1/dna/samples/{sample_id}/variants/{var_id}/relevant",
            headers=headers,
        )
        return payload

    def blacklist_dna_variant(
        self, sample_id: str, var_id: str, headers: dict[str, str] | None = None
    ) -> ApiPayload:
        payload = self._post(f"/api/v1/dna/samples/{sample_id}/variants/{var_id}/blacklist", headers=headers)
        return payload

    def hide_dna_variant_comment(
        self, sample_id: str, var_id: str, comment_id: str, headers: dict[str, str] | None = None
    ) -> ApiPayload:
        payload = self._post(
            f"/api/v1/dna/samples/{sample_id}/variants/{var_id}/comments/{comment_id}/hide",
            headers=headers,
        )
        return payload

    def unhide_dna_variant_comment(
        self, sample_id: str, var_id: str, comment_id: str, headers: dict[str, str] | None = None
    ) -> ApiPayload:
        payload = self._post(
            f"/api/v1/dna/samples/{sample_id}/variants/{var_id}/comments/{comment_id}/unhide",
            headers=headers,
        )
        return payload

    def set_dna_variants_false_positive_bulk(
        self,
        sample_id: str,
        variant_ids: list[str],
        apply: bool,
        headers: dict[str, str] | None = None,
    ) -> ApiPayload:
        payload = self._post(
            f"/api/v1/dna/samples/{sample_id}/variants/bulk/fp",
            headers=headers,
            params={"apply": str(bool(apply)).lower(), "variant_ids": variant_ids},
        )
        return payload

    def set_dna_variants_irrelevant_bulk(
        self,
        sample_id: str,
        variant_ids: list[str],
        apply: bool,
        headers: dict[str, str] | None = None,
    ) -> ApiPayload:
        payload = self._post(
            f"/api/v1/dna/samples/{sample_id}/variants/bulk/irrelevant",
            headers=headers,
            params={"apply": str(bool(apply)).lower(), "variant_ids": variant_ids},
        )
        return payload

    def set_dna_variants_tier_bulk(
        self,
        sample_id: str,
        variant_ids: list[str],
        assay_group: str | None,
        subpanel: str | None,
        tier: str | int | None,
        headers: dict[str, str] | None = None,
    ) -> ApiPayload:
        payload = self._post(
            f"/api/v1/dna/samples/{sample_id}/variants/bulk/tier",
            headers=headers,
            json_body={
                "variant_ids": variant_ids,
                "assay_group": assay_group,
                "subpanel": subpanel,
                "tier": tier,
            },
        )
        return payload

    def classify_dna_variant(
        self,
        sample_id: str,
        target_id: str,
        form_data: dict[str, Any],
        headers: dict[str, str] | None = None,
    ) -> ApiPayload:
        payload = self._post(
            f"/api/v1/dna/samples/{sample_id}/variants/classify",
            headers=headers,
            json_body={"id": target_id, "form_data": form_data},
        )
        return payload

    def remove_dna_variant_classification(
        self,
        sample_id: str,
        target_id: str,
        form_data: dict[str, Any],
        headers: dict[str, str] | None = None,
    ) -> ApiPayload:
        payload = self._post(
            f"/api/v1/dna/samples/{sample_id}/variants/rmclassify",
            headers=headers,
            json_body={"id": target_id, "form_data": form_data},
        )
        return payload

    def add_dna_variant_comment(
        self,
        sample_id: str,
        target_id: str,
        form_data: dict[str, Any],
        headers: dict[str, str] | None = None,
    ) -> ApiPayload:
        payload = self._post(
            f"/api/v1/dna/samples/{sample_id}/comments/add",
            headers=headers,
            json_body={"id": target_id, "form_data": form_data},
        )
        return payload

