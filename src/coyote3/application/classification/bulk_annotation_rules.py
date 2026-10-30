"""Render governed bulk annotation templates from reusable finding facts."""

from typing import Any

from coyote3.application.reporting.clinical_rules.evaluator import condition_matches, render_rule
from coyote3.config.knowledgebase_sources import oncokb_gene_url
from coyote3.contracts.schemas.clinical_rules import (
    BulkAnnotationGroupOption,
    BulkAnnotationPreviewRequest,
    BulkAnnotationPreviewResult,
    ClinicalRuleSetDoc,
)


def bulk_annotation_group_options(groups: list[dict[str, Any]]) -> list[BulkAnnotationGroupOption]:
    """Build every registered group's complete leaf-to-root path without inferring parents.

    Args:
        groups: Registry documents, including inactive groups used by historical scopes.

    Returns:
        Safe group metadata sorted by root-to-leaf display path.

    Raises:
        ValueError: A hierarchy contains a missing parent, repeated identifier or cycle.
    """
    if any(
        not isinstance(group.get("group_id"), str) or not group["group_id"].strip()
        for group in groups
    ):
        raise ValueError("Biological group records require nonempty identifiers")
    by_id = {group["group_id"]: group for group in groups}
    if len(by_id) != len(groups):
        raise ValueError("Biological group identifiers must be unique")
    options = []
    for group_id, group in by_id.items():
        path_ids: list[str] = []
        path_names: list[str] = []
        current: str | None = group_id
        while current is not None:
            if current in path_ids:
                raise ValueError(f"Biological group hierarchy contains a cycle at '{current}'")
            node = by_id.get(current)
            if node is None:
                raise ValueError(f"Biological group parent '{current}' is not registered")
            path_ids.append(current)
            path_names.append(str(node.get("display_name") or current))
            current = node.get("parent_group_id")
        options.append(
            BulkAnnotationGroupOption(
                group_id=group_id,
                display_name=path_names[0],
                parent_group_id=group.get("parent_group_id"),
                path_ids=path_ids,
                path_names=path_names,
                is_active=group.get("is_active", True),
            )
        )
    return sorted(options, key=lambda item: tuple(reversed(item.path_names)))


def _biological_group_scope(
    group_id: str | None, groups: list[BulkAnnotationGroupOption]
) -> dict[str, Any]:
    """Expose registered hierarchy values, leaving unavailable group facts unknown.

    Args:
        group_id: Selected biological registry ID; None means no group context.
        groups: Validated complete hierarchy options.

    Returns:
        Group ID/name, immediate parent, all ancestors and root values for annotation rules.

    Raises:
        ValueError: A selected group is not registered.
    """
    group = next((item for item in groups if item.group_id == group_id), None)
    if group_id is not None and group is None:
        raise ValueError(f"Biological group '{group_id}' is not registered")
    ids = group.path_ids if group else []
    names = group.path_names if group else []
    return {
        "asp_group": group_id,
        "group_name": group.display_name if group else None,
        "parent_group_id": ids[1] if len(ids) > 1 else None,
        "parent_group_name": names[1] if len(names) > 1 else None,
        "ancestor_group_ids": ids[1:],
        "ancestor_group_names": names[1:],
        "group_path_ids": ids,
        "group_path_names": names,
        "root_group_id": ids[-1] if ids else None,
        "root_group_name": names[-1] if names else None,
    }


def render_bulk_annotation(
    release: ClinicalRuleSetDoc,
    facts: BulkAnnotationPreviewRequest,
    *,
    diagnosis_id: str | None = None,
    groups: list[BulkAnnotationGroupOption] | None = None,
) -> BulkAnnotationPreviewResult:
    """Render the first enabled matching template for the requested tier.

    Args:
        release: Validated scoped rule version, published for persisted annotations.
        facts: Finding-level values, optional preview diagnosis and the explicitly chosen tier.
        diagnosis_id: Actual sample scope when a Base release supplies the template;
            None uses the release scope for synthetic preview.
        groups: Registered biological hierarchy; None supplies no group options.

    Returns:
        Matching rule identifier and text, or null values when no template matches.

    Raises:
        ValueError: A matched template has missing required values or empty output.

    Notes:
        No sample measurements, identifiers or patient information enter the scope.
        This function neither assigns tiers nor writes annotations.
    """
    scope: dict[str, Any] = {
        "sample": {
            "asp_id": release.scope.asp_id,
            "diagnosis_id": diagnosis_id or facts.diagnosis_id or release.scope.diagnosis_id,
        },
        "finding": facts.model_dump(),
        "asp": _biological_group_scope(facts.asp_group, groups or []),
        "annotation": {
            "consequence_text": facts.consequence[0].replace("_", " ")
            if facts.consequence
            else None,
            "consequence_labels": [value.replace("_", " ") for value in facts.consequence],
            "oncokb_gene_present": facts.oncokb_gene_present,
            "oncokb_gene_url": oncokb_gene_url(facts.gene)
            if facts.gene and facts.oncokb_gene_present
            else None,
            "oncokb_gene_description": facts.oncokb_gene_description
            if facts.oncokb_gene_present
            else None,
        },
    }
    for rule in sorted(release.bulk_annotation_rules, key=lambda item: item.order):
        if not rule.enabled or rule.tier != facts.tier:
            continue
        matched, missing = condition_matches(rule.condition, scope)
        if not matched or missing:
            continue
        text = render_rule(rule, scope=scope, terminology={}).strip()
        if not text:
            raise ValueError(f"Annotation rule '{rule.rule_id}' produced empty text")
        return BulkAnnotationPreviewResult(rule_id=rule.rule_id, text=text)
    return BulkAnnotationPreviewResult()
