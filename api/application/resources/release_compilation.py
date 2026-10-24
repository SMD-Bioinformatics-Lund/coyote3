"""Compile operational configurations from validated installation resource bundles."""

from typing import Any

from api.application.common.release_resources import capture_assay_resource, capture_gene_lists
from api.application.query_rules.compilation import compile_query_policies
from api.application.query_rules.service import QueryRuleService
from api.application.reporting.clinical_rules.resolution import resolve_published_rule_set
from api.contracts.schemas.query_rules import QueryRuleScope


class BundleQueryPolicies:
    """Resolve staged policy releases over an optional installed authoring repository."""

    def __init__(self, rows: list[dict[str, Any]], repository: Any) -> None:
        """Bind validated staged records and the source repository, or None for offline compilation."""
        self.rows = rows
        self.repository = repository

    def published_for(self, scope: dict[str, Any]) -> list[dict[str, Any]]:
        """Return matching staged publications and unaffected installed ancestors."""
        ancestors = {item.key() for item in QueryRuleScope.model_validate(scope).ancestors()}
        packaged = {
            row["scope_key"]: row
            for row in self.rows
            if row["status"] == "published" and row["scope_key"] in ancestors
        }
        existing = self.repository.published_for(scope) if self.repository else []
        return [row for row in existing if row["scope_key"] not in packaged] + list(
            packaged.values()
        )


class BundleClinicalRules:
    """Expose staged clinical rule revisions to the standard release selector."""

    def __init__(self, rows: list[dict[str, Any]]) -> None:
        """Bind validated staged documents without consulting installed mutable rules."""
        self.rows = rows

    def list_active_for_assay(self, asp_id: str, **scope: Any) -> list[dict[str, Any]]:
        """Return active assay candidates for the standard scope and integrity checks."""
        return [row for row in self.rows if row["scope"]["asp_id"] == asp_id and row["active"]]


def compile_bundle_configurations(documents: dict[str, list[dict]], repository: Any = None) -> None:
    """Compile staged configuration artifacts before installation writes any records.

    Args:
        documents: Validated resource bundle; configuration artifacts are populated in place.
        repository: Installed query-rule source, or None for a self-contained offline bundle.

    Raises:
        AppError: A selected resource or reporting policy cannot be resolved unambiguously.
        KeyError: A configuration references an assay absent from the bundle.
        ValueError: A named diagnosis lacks its definition or explicit assay association.
    """
    panels = {panel["asp_id"]: panel for panel in documents.get("assay_specific_panels", [])}
    definitions = {
        row["diagnosis_id"] for row in documents.get("diagnoses", []) if row.get("is_active", True)
    }
    associations = {
        (row["asp_id"], row["diagnosis_id"])
        for row in documents.get("diagnosis_associations", [])
        if row.get("is_active", True)
    }
    rules = QueryRuleService(BundleQueryPolicies(documents.get("query_rule_sets", []), repository))
    for configuration in documents.get("asp_configs", []):
        panel = panels[configuration["asp_id"]]
        diagnosis = configuration["diagnosis_id"]
        if diagnosis != "base" and (
            diagnosis not in definitions or (panel["asp_id"], diagnosis) not in associations
        ):
            raise ValueError(
                "Configuration requires an explicit shared diagnosis and assay association"
            )
        configuration["assay_resource_release"] = capture_assay_resource(panel)
        configuration["gene_list_release"] = capture_gene_lists(
            [
                item
                for item in documents.get("insilico_genelists", [])
                if item.get("is_active")
                and not item.get("adhoc")
                and (
                    configuration["asp_id"] in (item.get("asp_ids") or [])
                    or configuration["asp_group"] in (item.get("asp_groups") or [])
                )
            ]
        )
        configuration["query_policy_release"] = compile_query_policies(configuration, panel, rules)
        configuration["clinical_rule_release"] = None
        if configuration.get("reporting", {}).get("report_sections"):
            configuration["clinical_rule_release"] = resolve_published_rule_set(
                BundleClinicalRules(documents.get("clinical_rule_sets", [])),
                asp_id=configuration["asp_id"],
                diagnosis_id=configuration["diagnosis_id"],
                analyte=configuration["asp_category"],
                language=configuration["reporting"]["language"],
            ).model_dump(mode="python", by_alias=True)
