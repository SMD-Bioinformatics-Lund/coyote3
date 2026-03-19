"""DNA route helper service."""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from api.core.dna.dna_filters import cnv_organizegenes, cnvtype_variant, create_cnveffectlist
from api.core.dna.query_builders import build_cnv_query
from api.http import api_error
from api.repositories.dna_repository import DnaRouteRepository
from api.services.dna_export import (
    build_cnv_export_rows as _build_cnv_export_rows,
)
from api.services.dna_export import (
    build_snv_export_rows as _build_snv_export_rows,
)
from api.services.dna_export import (
    build_transloc_export_rows as _build_transloc_export_rows,
)
from api.services.dna_export import (
    consequence_list,
)
from api.services.dna_export import (
    export_rows_to_csv as _export_rows_to_csv,
)
from api.services.dna_payloads import (
    biomarkers_payload as _biomarkers_payload,
)
from api.services.dna_payloads import (
    list_variants_payload as _list_variants_payload,
)
from api.services.dna_payloads import (
    plot_context_payload as _plot_context_payload,
)
from api.services.dna_payloads import (
    variant_context_payload as _variant_context_payload,
)


class DnaService:
    """Own shared DNA, CNV, and small-variant support workflows."""

    def __init__(self, repository: DnaRouteRepository | None = None) -> None:
        """Initialize the service with repository dependencies.

        Args:
                repository: Repository. Optional argument.
        """
        self.repository = repository or DnaRouteRepository()

    @staticmethod
    def export_rows_to_csv(rows: list[Any]) -> str:
        """Serialize export rows into CSV text with stable column ordering."""
        return _export_rows_to_csv(rows)

    def build_snv_export_rows(self, variants: list[dict[str, Any]]) -> list[Any]:
        """Build typed SNV export rows from filtered variant documents."""
        return _build_snv_export_rows(variants)

    def build_cnv_export_rows(
        self, cnvs: list[dict[str, Any]], sample: dict[str, Any], assay_group: str
    ) -> list[Any]:
        """Build typed CNV export rows from filtered CNV documents."""
        return _build_cnv_export_rows(cnvs, sample, assay_group)

    def build_transloc_export_rows(self, translocs: list[dict[str, Any]]) -> list[Any]:
        """Build typed translocation export rows from filtered translocation documents."""
        return _build_transloc_export_rows(translocs)

    @staticmethod
    def mutation_payload(
        sample_id: str, resource: str, resource_id: str, action: str
    ) -> dict[str, Any]:
        """Build a standard mutation response payload.

        Args:
            sample_id (str): Value for ``sample_id``.
            resource (str): Value for ``resource``.
            resource_id (str): Value for ``resource_id``.
            action (str): Value for ``action``.

        Returns:
            dict[str, Any]: The function result.
        """
        return {
            "status": "ok",
            "sample_id": str(sample_id),
            "resource": resource,
            "resource_id": str(resource_id),
            "action": action,
            "meta": {"status": "updated"},
        }

    def load_cnvs_for_sample(
        self, *, sample: dict, sample_filters: dict, filter_genes: list[str]
    ) -> list[dict]:
        """Load cnvs for sample.

        Args:
            sample (dict): Value for ``sample``.
            sample_filters (dict): Value for ``sample_filters``.
            filter_genes (list[str]): Value for ``filter_genes``.

        Returns:
            list[dict]: The function result.
        """
        cnv_query = build_cnv_query(
            str(sample["_id"]), filters={**sample_filters, "filter_genes": filter_genes}
        )
        cnvs = list(self.repository.cnv_handler.get_sample_cnvs(cnv_query))
        filter_cnveffects = create_cnveffectlist(sample_filters.get("cnveffects", []))
        if filter_cnveffects:
            cnvs = cnvtype_variant(cnvs, filter_cnveffects)
        return cnv_organizegenes(cnvs)

    def require_variant_for_sample(self, *, sample: dict, var_id: str) -> dict:
        """Load a variant and assert it belongs to the provided sample.

        Args:
            sample (dict): Value for ``sample``.
            var_id (str): Value for ``var_id``.

        Returns:
            dict: The function result.
        """
        variant = self.repository.variant_handler.get_variant(var_id)
        if not variant or str(variant.get("SAMPLE_ID", "")) != str(sample.get("_id")):
            raise api_error(404, "Variant not found for sample")
        return variant

    def set_variant_bulk_flag(self, *, resource_ids: list[str], apply: bool, flag: str) -> None:
        """Set variant bulk flag.

        Args:
            resource_ids (list[str]): Value for ``resource_ids``.
            apply (bool): Value for ``apply``.
            flag (str): Value for ``flag``.

        Returns:
            None.
        """
        if not resource_ids:
            return
        if flag == "false_positive":
            if apply:
                self.repository.variant_handler.mark_false_positive_var_bulk(resource_ids)
            else:
                self.repository.variant_handler.unmark_false_positive_var_bulk(resource_ids)
            return
        if flag == "irrelevant":
            if apply:
                self.repository.variant_handler.mark_irrelevant_var_bulk(resource_ids)
            else:
                self.repository.variant_handler.unmark_irrelevant_var_bulk(resource_ids)
            return
        raise ValueError(f"Unsupported flag: {flag}")

    def set_variant_tier_bulk(
        self,
        *,
        sample: dict,
        resource_ids: list[str],
        assay_group: str | None,
        subpanel: str | None,
        apply: bool,
        class_num: int,
        create_annotation_text_fn,
        create_classified_variant_doc_fn,
    ) -> None:
        """Set variant tier bulk.

        Args:
            sample (dict): Value for ``sample``.
            resource_ids (list[str]): Value for ``resource_ids``.
            assay_group (str | None): Value for ``assay_group``.
            subpanel (str | None): Value for ``subpanel``.
            apply (bool): Value for ``apply``.
            class_num (int): Value for ``class_num``.
            create_annotation_text_fn: Value for ``create_annotation_text_fn``.
            create_classified_variant_doc_fn: Value for ``create_classified_variant_doc_fn``.

        Returns:
            None.
        """
        bulk_docs: list[dict[str, Any]] = []
        for variant_id in resource_ids:
            var = self.repository.variant_handler.get_variant(str(variant_id))
            if not var:
                continue
            if str(var.get("SAMPLE_ID")) != str(sample.get("_id")):
                continue

            selected_csq = var.get("INFO", {}).get("selected_CSQ", {})
            transcript = selected_csq.get("Feature")
            gene = selected_csq.get("SYMBOL")
            hgvs_p = selected_csq.get("HGVSp")
            hgvs_c = selected_csq.get("HGVSc")
            hgvs_g = f"{var['CHROM']}:{var['POS']}:{var['REF']}/{var['ALT']}"
            consequence = consequence_list(selected_csq.get("Consequence"))
            gene_oncokb = self.repository.oncokb_handler.get_oncokb_gene(gene)
            text = create_annotation_text_fn(
                gene, consequence, assay_group, gene_oncokb=gene_oncokb
            )

            nomenclature = "p"
            if hgvs_p not in {"", None}:
                variant = hgvs_p
            elif hgvs_c not in {"", None}:
                variant = hgvs_c
                nomenclature = "c"
            else:
                variant = hgvs_g
                nomenclature = "g"

            variant_data = {
                "gene": gene,
                "assay_group": assay_group,
                "subpanel": subpanel,
                "transcript": transcript,
            }

            if not apply:
                self.repository.annotation_handler.delete_classified_variant(
                    variant=variant,
                    nomenclature=nomenclature,
                    variant_data=variant_data,
                    class_num=class_num,
                    annotation_text=text,
                )
                continue

            bulk_docs.append(
                deepcopy(
                    create_classified_variant_doc_fn(
                        variant=variant,
                        nomenclature=nomenclature,
                        class_num=class_num,
                        variant_data=variant_data,
                    )
                )
            )
            bulk_docs.append(
                deepcopy(
                    create_classified_variant_doc_fn(
                        variant=variant,
                        nomenclature=nomenclature,
                        class_num=class_num,
                        variant_data=variant_data,
                        text=text,
                        source="bulk_tier_default_text",
                    )
                )
            )

        if bulk_docs:
            self.repository.annotation_handler.insert_annotation_bulk(bulk_docs)

    def classify_variant(
        self, *, form_data: dict, get_tier_classification_fn, get_variant_nomenclature_fn
    ) -> None:
        """Classify a variant and persist classification documents.

        Args:
            form_data (dict): Value for ``form_data``.
            get_tier_classification_fn: Value for ``get_tier_classification_fn``.
            get_variant_nomenclature_fn: Value for ``get_variant_nomenclature_fn``.

        Returns:
            None.
        """
        class_num = get_tier_classification_fn(form_data)
        nomenclature, variant = get_variant_nomenclature_fn(form_data)
        if class_num != 0:
            self.repository.annotation_handler.insert_classified_variant(
                variant, nomenclature, class_num, form_data
            )

    def remove_classified_variant(self, *, form_data: dict, get_variant_nomenclature_fn) -> None:
        """Remove classified variant.

        Args:
            form_data (dict): Value for ``form_data``.
            get_variant_nomenclature_fn: Value for ``get_variant_nomenclature_fn``.

        Returns:
            None.
        """
        nomenclature, variant = get_variant_nomenclature_fn(form_data)
        self.repository.annotation_handler.delete_classified_variant(
            variant, nomenclature, form_data
        )

    def add_variant_comment(
        self, *, form_data: dict, target_id: str, get_variant_nomenclature_fn, create_comment_doc_fn
    ) -> str:
        """Create a variant/fusion/translocation/CNV comment and return its resource type.

        Args:
            form_data (dict): Value for ``form_data``.
            target_id (str): Value for ``target_id``.
            get_variant_nomenclature_fn: Value for ``get_variant_nomenclature_fn``.
            create_comment_doc_fn: Value for ``create_comment_doc_fn``.

        Returns:
            str: The function result.
        """
        nomenclature, variant = get_variant_nomenclature_fn(form_data)
        doc = create_comment_doc_fn(form_data, nomenclature=nomenclature, variant=variant)
        comment_scope = form_data.get("global")
        if comment_scope == "global":
            self.repository.annotation_handler.add_anno_comment(doc)
        if nomenclature == "f":
            if comment_scope != "global":
                self.repository.fusion_handler.add_fusion_comment(target_id, doc)
            return "fusion_comment"
        if nomenclature == "t":
            if comment_scope != "global":
                self.repository.transloc_handler.add_transloc_comment(target_id, doc)
            return "translocation_comment"
        if nomenclature == "cn":
            if comment_scope != "global":
                self.repository.cnv_handler.add_cnv_comment(target_id, doc)
            return "cnv_comment"
        if comment_scope != "global":
            self.repository.variant_handler.add_var_comment(target_id, doc)
        return "variant_comment"

    def list_variants_payload(
        self,
        *,
        request,
        sample: dict,
        util_module,
        add_global_annotations_fn,
        generate_summary_text_fn,
        build_query_fn,
        get_filter_conseq_terms_fn,
        assay_config_getter,
    ) -> dict[str, Any]:
        """List variants payload.

        Args:
            request: Value for ``request``.
            sample (dict): Value for ``sample``.
            util_module: Value for ``util_module``.
            add_global_annotations_fn: Value for ``add_global_annotations_fn``.
            generate_summary_text_fn: Value for ``generate_summary_text_fn``.
            build_query_fn: Value for ``build_query_fn``.
            get_filter_conseq_terms_fn: Value for ``get_filter_conseq_terms_fn``.
            assay_config_getter: Value for ``assay_config_getter``.

        Returns:
            dict[str, Any]: The function result.
        """
        return _list_variants_payload(
            service=self,
            request=request,
            sample=sample,
            util_module=util_module,
            add_global_annotations_fn=add_global_annotations_fn,
            generate_summary_text_fn=generate_summary_text_fn,
            build_query_fn=build_query_fn,
            get_filter_conseq_terms_fn=get_filter_conseq_terms_fn,
            assay_config_getter=assay_config_getter,
        )

    def plot_context_payload(self, *, sample: dict, assay_config_getter) -> dict[str, Any]:
        """Build plot context payload for DNA routes.

        Args:
            sample (dict): Value for ``sample``.
            assay_config_getter: Value for ``assay_config_getter``.

        Returns:
            dict[str, Any]: The function result.
        """
        return _plot_context_payload(
            service=self,
            sample=sample,
            assay_config_getter=assay_config_getter,
        )

    def biomarkers_payload(self, *, sample: dict) -> dict[str, Any]:
        """Build biomarker payload for DNA routes.

        Args:
            sample (dict): Value for ``sample``.

        Returns:
            dict[str, Any]: The function result.
        """
        return _biomarkers_payload(service=self, sample=sample)

    def variant_context_payload(
        self,
        *,
        sample: dict,
        var_id: str,
        add_alt_class_fn,
        util_module,
        assay_config_getter,
    ) -> dict[str, Any]:
        """Build single-variant context payload for DNA routes.

        Args:
            sample (dict): Value for ``sample``.
            var_id (str): Value for ``var_id``.
            add_alt_class_fn: Value for ``add_alt_class_fn``.
            util_module: Value for ``util_module``.
            assay_config_getter: Value for ``assay_config_getter``.

        Returns:
            dict[str, Any]: The function result.
        """
        return _variant_context_payload(
            service=self,
            sample=sample,
            var_id=var_id,
            add_alt_class_fn=add_alt_class_fn,
            util_module=util_module,
            assay_config_getter=assay_config_getter,
        )

    @staticmethod
    def coerce_bool(value: object, default: bool = True) -> bool:
        """Convert arbitrary input into a boolean.

        Args:
            value (object): Value for ``value``.
            default (bool): Value for ``default``.

        Returns:
            bool: The function result.
        """
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            lowered = value.strip().lower()
            if lowered in {"true", "1", "yes", "on"}:
                return True
            if lowered in {"false", "0", "no", "off"}:
                return False
        return default
