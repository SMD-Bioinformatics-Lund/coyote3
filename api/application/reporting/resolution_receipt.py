"""Capture the resolved inputs used to prepare a saved clinical report."""

from copy import deepcopy
from typing import Any

from api.application.common.release_resources import assay_resource, gene_list_resources
from api.application.reporting.report_renderer import template_content_hash
from api.domain.common.assay_filters import get_sample_effective_genes
from api.version import __version__


def report_resolution_receipt(template: str, context: dict[str, Any]) -> dict[str, Any]:
    """Capture configuration, settings, reference versions and rendering provenance.

    Args:
        template: Registered template selected for rendering.
        context: Prepared inputs shared by preview validation and report rendering.

    Returns:
        Independent receipt retained with the report rather than re-resolved at save time.
    """
    sample = context["sample"]
    configuration = context["assay_config"]
    panel = assay_resource(configuration)
    scopes = {}
    for intent, targets in (sample.get("filters") or {}).items():
        for target, values in targets.items():
            list_key = {
                "snv": "snvlists",
                "cnv": "cnvlists",
                "fusion": "fusionlists",
                "translocation": "fusionlists",
            }.get(target)
            if list_key is None:
                continue
            selected = gene_list_resources(configuration, values.get(list_key) or [])
            lists, genes = get_sample_effective_genes(sample, panel, selected, target, intent)
            scopes[f"{intent}:{target}"] = {
                "state": "restricted" if genes else "empty",
                "genes": genes,
                "lists": [
                    {"id": key, "version": value.get("version")} for key, value in selected.items()
                ],
                "excluded": [
                    {"gene": gene, "reason": "outside_assay_eligibility"}
                    for gene in sorted(
                        {gene for value in lists.values() for gene in value.get("uncovered", [])}
                    )
                ],
            }
    return deepcopy(
        {
            "context": configuration.get("aspc_resolution"),
            "configuration": configuration,
            "environment": sample.get("environment"),
            "annotation_namespace": "clinical"
            if sample.get("environment") == "production"
            else "sandbox",
            "sample_version": sample.get("version", 1),
            "filters": {
                "defaults": configuration.get("filters"),
                "effective": sample.get("filters"),
                "provenance": sample.get("settings_provenance"),
                "overrides": [
                    {
                        "intent": intent,
                        "analysis": target,
                        "field": field,
                        "default": configuration.get("filters", {})
                        .get(intent, {})
                        .get(target, {})
                        .get(field),
                        "effective": value,
                    }
                    for intent, targets in (sample.get("filters") or {}).items()
                    for target, values in targets.items()
                    for field, value in values.items()
                    if value
                    != configuration.get("filters", {}).get(intent, {}).get(target, {}).get(field)
                ],
            },
            "query_policy": configuration.get("query_policy_release"),
            "clinical_rules": configuration.get("clinical_rule_release"),
            "gene_lists": configuration.get("gene_list_release"),
            "gene_scopes": scopes,
            "source_database_versions": sample.get("database_versions"),
            "input_files": sample.get("files"),
            "pipeline": {
                "name": sample.get("pipeline"),
                "version": sample.get("pipeline_version"),
            },
            "genome_build": sample.get("genome_build"),
            "rendering": {
                "template": template,
                "content_hash": template_content_hash(template),
                "software_version": __version__,
                "language": configuration.get("reporting", {}).get("language"),
            },
        }
    )
