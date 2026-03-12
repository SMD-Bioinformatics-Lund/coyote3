"""DNA route helper service."""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from api.core.dna.dna_filters import cnv_organizegenes, cnvtype_variant, create_cnveffectlist
from api.core.dna.dna_reporting import hotspot_variant
from api.core.dna.dna_variants import format_pon
from api.core.dna.notation import one_letter_p
from api.core.dna.query_builders import build_cnv_query
from api.http import api_error, get_formatted_assay_config
from api.repositories.dna_repository import DnaRouteRepository


class DnaService:
    def __init__(self, repository: DnaRouteRepository | None = None) -> None:
        self.repository = repository or DnaRouteRepository()

    @staticmethod
    def mutation_payload(sample_id: str, resource: str, resource_id: str, action: str) -> dict[str, Any]:
        return {
            "status": "ok",
            "sample_id": str(sample_id),
            "resource": resource,
            "resource_id": str(resource_id),
            "action": action,
            "meta": {"status": "updated"},
        }

    def load_cnvs_for_sample(self, *, sample: dict, sample_filters: dict, filter_genes: list[str]) -> list[dict]:
        cnv_query = build_cnv_query(str(sample["_id"]), filters={**sample_filters, "filter_genes": filter_genes})
        cnvs = list(self.repository.cnv_handler.get_sample_cnvs(cnv_query))
        filter_cnveffects = create_cnveffectlist(sample_filters.get("cnveffects", []))
        if filter_cnveffects:
            cnvs = cnvtype_variant(cnvs, filter_cnveffects)
        return cnv_organizegenes(cnvs)

    def require_variant_for_sample(self, *, sample: dict, var_id: str) -> dict:
        variant = self.repository.variant_handler.get_variant(var_id)
        if not variant or str(variant.get("SAMPLE_ID", "")) != str(sample.get("_id")):
            raise api_error(404, "Variant not found for sample")
        return variant

    def set_variant_bulk_flag(self, *, resource_ids: list[str], apply: bool, flag: str) -> None:
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
            consequence = selected_csq.get("Consequence")
            gene_oncokb = self.repository.oncokb_handler.get_oncokb_gene(gene)
            text = create_annotation_text_fn(gene, consequence, assay_group, gene_oncokb=gene_oncokb)

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

    def classify_variant(self, *, form_data: dict, get_tier_classification_fn, get_variant_nomenclature_fn) -> None:
        class_num = get_tier_classification_fn(form_data)
        nomenclature, variant = get_variant_nomenclature_fn(form_data)
        if class_num != 0:
            self.repository.annotation_handler.insert_classified_variant(variant, nomenclature, class_num, form_data)

    def remove_classified_variant(self, *, form_data: dict, get_variant_nomenclature_fn) -> None:
        nomenclature, variant = get_variant_nomenclature_fn(form_data)
        self.repository.annotation_handler.delete_classified_variant(variant, nomenclature, form_data)

    def add_variant_comment(self, *, form_data: dict, target_id: str, get_variant_nomenclature_fn, create_comment_doc_fn) -> str:
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
        assay_config = assay_config_getter(sample)
        if not assay_config:
            raise api_error(404, "Assay config not found for sample")

        sample = util_module.common.merge_sample_settings_with_assay_config(sample, assay_config)
        sample_filters = deepcopy(sample.get("filters", {}))
        assay_group = assay_config.get("asp_group", "unknown")
        subpanel = sample.get("subpanel")
        analysis_sections = assay_config.get("analysis_types", [])

        assay_panel_doc = self.repository.asp_handler.get_asp(asp_name=sample.get("assay"))
        checked_genelists = sample_filters.get("genelists", [])
        checked_genelists_genes_dict = self.repository.isgl_handler.get_isgl_by_ids(checked_genelists)
        genes_covered_in_panel, filter_genes = util_module.common.get_sample_effective_genes(
            sample, assay_panel_doc, checked_genelists_genes_dict
        )
        filter_conseq = get_filter_conseq_terms_fn(sample_filters.get("vep_consequences", []))

        disp_pos = []
        verification_sample_used = None
        if assay_config.get("verification_samples"):
            for veri_key, verification_pos in assay_config.get("verification_samples", {}).items():
                if veri_key in sample.get("name", ""):
                    disp_pos = verification_pos
                    verification_sample_used = veri_key
                    break

        query = build_query_fn(
            assay_group,
            {
                "id": str(sample["_id"]),
                "max_freq": sample_filters["max_freq"],
                "min_freq": sample_filters["min_freq"],
                "max_control_freq": sample_filters["max_control_freq"],
                "min_depth": sample_filters["min_depth"],
                "min_alt_reads": sample_filters["min_alt_reads"],
                "max_popfreq": sample_filters["max_popfreq"],
                "filter_conseq": filter_conseq,
                "filter_genes": filter_genes,
                "disp_pos": disp_pos,
            },
        )

        variants = list(self.repository.variant_handler.get_case_variants(query))
        variants = self.repository.blacklist_handler.add_blacklist_data(variants, assay_group)
        variants, tiered_variants = add_global_annotations_fn(variants, assay_group, subpanel)
        variants = hotspot_variant(variants)

        sample_ids = util_module.common.get_case_and_control_sample_ids(sample)
        bam_id = self.repository.bam_service_handler.get_bams(sample_ids)
        vep_variant_class_meta = self.repository.vep_meta_handler.get_variant_class_translations(sample.get("vep", 103))
        vep_conseq_meta = self.repository.vep_meta_handler.get_conseq_translations(sample.get("vep", 103))
        has_hidden_comments = self.repository.sample_handler.hidden_sample_comments(sample.get("_id"))
        insilico_panel_genelists = self.repository.isgl_handler.get_isgl_by_asp(sample.get("assay"), is_active=True)
        all_panel_genelist_names = util_module.common.get_assay_genelist_names(insilico_panel_genelists)
        assay_config_schema = self.repository.schema_handler.get_schema(assay_config.get("schema_name"))

        oncokb_genes = []
        for variant in variants:
            symbol = variant.get("INFO", {}).get("selected_CSQ", {}).get("SYMBOL")
            if not symbol:
                continue
            oncokb_gene = self.repository.oncokb_handler.get_oncokb_action_gene(symbol)
            if oncokb_gene and "Hugo Symbol" in oncokb_gene:
                hugo_symbol = oncokb_gene["Hugo Symbol"]
                if hugo_symbol not in oncokb_genes:
                    oncokb_genes.append(hugo_symbol)

        display_sections_data = {"snvs": deepcopy(variants)}
        summary_sections_data = {"snvs": tiered_variants}

        if "CNV" in analysis_sections:
            cnvs = self.load_cnvs_for_sample(sample=sample, sample_filters=sample_filters, filter_genes=filter_genes)
            display_sections_data["cnvs"] = deepcopy(cnvs)
            summary_sections_data["cnvs"] = [cnv for cnv in cnvs if cnv.get("interesting")]

        if "BIOMARKER" in analysis_sections:
            biomarkers = list(self.repository.biomarker_handler.get_sample_biomarkers(sample_id=str(sample["_id"])))
            display_sections_data["biomarkers"] = biomarkers
            summary_sections_data["biomarkers"] = biomarkers

        if "TRANSLOCATION" in analysis_sections:
            translocs = list(self.repository.transloc_handler.get_sample_translocations(sample_id=str(sample["_id"])))
            display_sections_data["translocs"] = translocs

        if "FUSION" in analysis_sections:
            display_sections_data["fusions"] = []
            summary_sections_data["translocs"] = [
                transloc for transloc in display_sections_data.get("translocs", []) if transloc.get("interesting")
            ]

        if "cnv" in sample and str(sample["cnv"]).lower().endswith((".png", ".jpg", ".jpeg")):
            sample["cnvprofile"] = sample["cnv"]

        ai_text = generate_summary_text_fn(
            sample_ids,
            assay_config,
            assay_panel_doc,
            summary_sections_data,
            filter_genes,
            checked_genelists,
        )

        return {
            "sample": sample,
            "meta": {"request_path": request.url.path, "count": len(variants), "tiered": tiered_variants},
            "filters": sample_filters,
            "assay_group": assay_group,
            "subpanel": subpanel,
            "analysis_sections": analysis_sections,
            "assay_config": assay_config,
            "assay_config_schema": assay_config_schema,
            "assay_panel_doc": assay_panel_doc,
            "assay_panels": insilico_panel_genelists,
            "all_panel_genelist_names": all_panel_genelist_names,
            "checked_genelists": checked_genelists,
            "checked_genelists_dict": genes_covered_in_panel,
            "filter_genes": filter_genes,
            "sample_ids": sample_ids,
            "bam_id": bam_id,
            "hidden_comments": has_hidden_comments,
            "vep_var_class_translations": vep_variant_class_meta,
            "vep_conseq_translations": vep_conseq_meta,
            "oncokb_genes": oncokb_genes,
            "verification_sample_used": verification_sample_used,
            "variants": variants,
            "display_sections_data": display_sections_data,
            "ai_text": ai_text,
        }

    def plot_context_payload(self, *, sample: dict, assay_config_getter) -> dict[str, Any]:
        assay_config = assay_config_getter(sample)
        if not assay_config:
            raise api_error(404, "Assay config not found for sample")
        assay_config_schema = self.repository.schema_handler.get_schema(assay_config.get("schema_name"))
        return {
            "sample": sample,
            "assay_config": assay_config,
            "assay_config_schema": assay_config_schema,
            "plots_base_dir": assay_config.get("reporting", {}).get("plots_path", None),
        }

    def biomarkers_payload(self, *, sample: dict) -> dict[str, Any]:
        biomarkers = list(self.repository.biomarker_handler.get_sample_biomarkers(sample_id=str(sample["_id"])))
        return {"sample": sample, "meta": {"count": len(biomarkers)}, "biomarkers": biomarkers}

    def variant_context_payload(
        self,
        *,
        sample: dict,
        var_id: str,
        add_alt_class_fn,
        util_module,
        assay_config_getter,
    ) -> dict[str, Any]:
        variant = self.repository.variant_handler.get_variant(var_id)
        if not variant:
            raise api_error(404, "Variant not found")
        if str(variant.get("SAMPLE_ID", "")) != str(sample.get("_id")):
            raise api_error(404, "Variant not found for sample")

        assay_config = assay_config_getter(sample)
        if not assay_config:
            raise api_error(404, "Assay config not found for sample")
        assay_group = assay_config.get("asp_group", "unknown")
        subpanel = sample.get("subpanel")

        variant = self.repository.blacklist_handler.add_blacklist_data([variant], assay_group)[0]
        in_other = self.repository.variant_handler.get_variant_in_other_samples(variant)
        has_hidden_comments = self.repository.variant_handler.hidden_var_comments(var_id)
        annotations, latest_classification, other_classifications, annotations_interesting = (
            self.repository.annotation_handler.get_global_annotations(variant, assay_group, subpanel)
        )
        if not latest_classification or latest_classification.get("class") == 999:
            variant = add_alt_class_fn(variant, assay_group, subpanel)
        else:
            variant["additional_classifications"] = None

        expression = self.repository.expression_handler.get_expression_data(list(variant.get("transcripts", [])))
        selected_csq = variant.get("INFO", {}).get("selected_CSQ", {})
        variant_desc = "NOTHING_IN_HERE"
        if (
            selected_csq.get("SYMBOL") == "CALR"
            and selected_csq.get("EXON") == "9/9"
            and "frameshift_variant" in str(selected_csq.get("Consequence", ""))
        ):
            variant_desc = "EXON 9 FRAMESHIFT"
        if (
            selected_csq.get("SYMBOL") == "FLT3"
            and "SVLEN" in variant.get("INFO", {})
            and variant.get("INFO", {}).get("SVLEN", 0) > 10
        ):
            variant_desc = "ITD"

        civic = self.repository.civic_handler.get_civic_data(variant, variant_desc)
        civic_gene = self.repository.civic_handler.get_civic_gene_info(selected_csq.get("SYMBOL"))

        oncokb_hgvsp = []
        if selected_csq.get("HGVSp"):
            hgvsp = one_letter_p(selected_csq.get("HGVSp")).replace("p.", "")
            oncokb_hgvsp.append(hgvsp)
        if selected_csq.get("Consequence") in {
            "frameshift_variant",
            "stop_gained",
            "frameshift_deletion",
            "frameshift_insertion",
        }:
            oncokb_hgvsp.append("Truncating Mutations")

        oncokb = self.repository.oncokb_handler.get_oncokb_anno(variant, oncokb_hgvsp)
        oncokb_action = self.repository.oncokb_handler.get_oncokb_action(variant, oncokb_hgvsp)
        oncokb_gene = self.repository.oncokb_handler.get_oncokb_gene(selected_csq.get("SYMBOL"))
        brca_exchange = self.repository.brca_handler.get_brca_data(variant, assay_group)
        iarc_tp53 = self.repository.iarc_tp53_handler.find_iarc_tp53(variant)

        sample_ids = util_module.common.get_case_and_control_sample_ids(sample)
        return {
            "sample": sample,
            "sample_summary": {
                "id": str(sample.get("_id")),
                "name": sample.get("name"),
                "assay": sample.get("assay"),
                "assay_group": assay_group,
                "subpanel": subpanel,
            },
            "variant": variant,
            "annotations": annotations,
            "latest_classification": latest_classification,
            "other_classifications": other_classifications,
            "annotations_interesting": annotations_interesting,
            "in_other_samples": in_other,
            "in_other": in_other,
            "has_hidden_comments": has_hidden_comments,
            "hidden_comments": has_hidden_comments,
            "expression": expression,
            "civic": civic,
            "civic_gene": civic_gene,
            "oncokb": oncokb,
            "oncokb_action": oncokb_action,
            "oncokb_gene": oncokb_gene,
            "brca_exchange": brca_exchange,
            "iarc_tp53": iarc_tp53,
            "assay_group": assay_group,
            "subpanel": subpanel,
            "pon": format_pon(variant),
            "sample_ids": sample_ids,
            "bam_id": self.repository.bam_service_handler.get_bams(sample_ids),
            "vep_var_class_translations": self.repository.vep_meta_handler.get_variant_class_translations(sample.get("vep", 103)),
            "vep_conseq_translations": self.repository.vep_meta_handler.get_conseq_translations(sample.get("vep", 103)),
            "assay_group_mappings": self.repository.asp_handler.get_asp_group_mappings(),
        }

    @staticmethod
    def coerce_bool(value: object, default: bool = True) -> bool:
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            lowered = value.strip().lower()
            if lowered in {"true", "1", "yes", "on"}:
                return True
            if lowered in {"false", "0", "no", "off"}:
                return False
        return default
