"""Classification helpers for DNA service workflows."""

from __future__ import annotations

from copy import deepcopy

from api.services.dna.export import consequence_list


def set_variant_tier_bulk(
    service,
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
    """Apply or remove variant classifications in bulk."""
    bulk_docs: list[dict[str, object]] = []
    for variant_id in resource_ids:
        var = service.variant_handler.get_variant(str(variant_id))
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
        gene_oncokb = service.oncokb_handler.get_oncokb_gene(gene)
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
            service.annotation_handler.delete_classified_variant(
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
        service.annotation_handler.insert_annotation_bulk(bulk_docs)


def classify_variant(
    service, *, form_data: dict, get_tier_classification_fn, get_variant_nomenclature_fn
) -> None:
    """Classify a variant and persist classification documents."""
    class_num = get_tier_classification_fn(form_data)
    nomenclature, variant = get_variant_nomenclature_fn(form_data)
    if class_num != 0:
        service.annotation_handler.insert_classified_variant(
            variant, nomenclature, class_num, form_data
        )


def remove_classified_variant(service, *, form_data: dict, get_variant_nomenclature_fn) -> None:
    """Remove a classified variant document."""
    nomenclature, variant = get_variant_nomenclature_fn(form_data)
    service.annotation_handler.delete_classified_variant(variant, nomenclature, form_data)
