"""Plan subpanel identities from explicit assay configuration."""

from datetime import datetime, timezone

from api.config.constants import SUBPANEL_BASE_ID, normalize_clinical_identifier
from api.contracts.schemas.subpanels import AssaySubpanelDoc


def plan_subpanels(
    panels: list[dict], configs: list[dict], rules: list[dict], lists: list[dict], *, actor: str
) -> list[dict]:
    """Build deterministic identities from configuration records, never clinical samples.

    Args:
        panels: Assay revisions; the highest version supplies current group metadata.
        configs: Existing ASPC scopes, including historical revisions.
        rules: Existing clinical rule-set scopes.
        lists: Active ISGL metadata with assay/group scopes and diagnosis identifiers.
        actor: Operator attributed to the initial registry revision.

    Returns:
        Validated registry documents; names preserve source identifiers except Base.

    Raises:
        ValueError: A scope references an unknown assay or a noncanonical identifier.
            Identifier errors list the exact scope and expected form without renaming it.
    """
    assays = {}
    for panel in sorted(panels, key=lambda item: item.get("version", 1)):
        assays[panel["asp_id"]] = panel
    identities = set()
    for scope in [*configs, *(rule.get("scope", {}) for rule in rules)]:
        asp_id = scope.get("asp_id")
        if asp_id not in assays:
            raise ValueError("Configuration references an unknown assay; resolve before migration")
        identities.add((asp_id, scope.get("subpanel_id") or SUBPANEL_BASE_ID))
    for asp_id, panel in assays.items():
        for genelist in lists:
            if genelist.get("is_active") is not True:
                continue
            if asp_id in (genelist.get("asp_ids") or []) or panel.get("asp_group") in (
                genelist.get("asp_groups") or []
            ):
                identities.update(
                    (asp_id, value) for value in genelist.get("diagnosis", []) if value
                )
    identities = {identity for identity in identities if identity[1] != SUBPANEL_BASE_ID}
    now = datetime.now(timezone.utc)
    problems = []
    for asp_id, subpanel_id in sorted(identities):
        for field, value in (("asp_id", asp_id), ("subpanel_id", subpanel_id)):
            try:
                normalized = normalize_clinical_identifier(value)
            except ValueError:
                detail = "unsupported identifier format"
            else:
                if normalized == value:
                    continue
                detail = f"canonical form would be {normalized!r}"
            problems.append(
                f"asp_id={asp_id!r}, subpanel_id={subpanel_id!r}: {field}={value!r}; {detail}"
            )
    if problems:
        raise ValueError(
            "Existing identifiers require review; migration will not rename scope keys:\n"
            + "\n".join(f"- {problem}" for problem in problems)
            + "\nNo registry documents were written. Review the source ASP, ASPC, "
            "clinical-rule scope or ISGL diagnosis association before retrying."
        )
    return [
        AssaySubpanelDoc(
            asp_id=asp_id,
            subpanel_id=subpanel_id,
            display_name="Base" if subpanel_id == SUBPANEL_BASE_ID else subpanel_id,
            updated_by=actor,
            updated_on=now,
        ).model_dump(
            by_alias=True, exclude_none=True, exclude={"definition_version", "definition_is_active"}
        )
        for asp_id, subpanel_id in sorted(identities)
    ]
