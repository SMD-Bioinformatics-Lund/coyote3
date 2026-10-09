"""Prepare installed query rules from the application catalog and seed criteria."""

from copy import deepcopy
from datetime import datetime, timezone
from itertools import product
from pathlib import Path

from api.config.clinical_query_policy import exception_payload, load_clinical_query_policy
from api.config.paths import CLINICAL_QUERY_SEED_PATH
from api.contracts.schemas.query_rules import QueryRuleDoc, QueryRuleScope


def prepare_query_rule_seeds(
    catalog: list[dict],
    groups: list[dict],
    *,
    actor: str,
    policy_path: str | Path = CLINICAL_QUERY_SEED_PATH,
) -> list[dict]:
    """Merge bundled group rules and installation-only TOML exceptions into releases.

    Args:
        catalog: Bundled group releases in the current query-rule contract.
        groups: Registered group seed documents, used to reject unresolved references.
        actor: Initial administrator or installing operator recorded on all releases.
        policy_path: Application seed TOML; an explicit path supports offline fixture tests.

    Returns:
        Published version-one documents, including a global default scope when needed.
        Child exception lists include inherited installation criteria before local ones.

    Raises:
        ValueError: Group scope is unknown, unsupported PGX rules are supplied, or
            assay/subpanel rules need registries that do not exist at first installation.
        RuntimeError: TOML content does not satisfy the supported policy grammar.
    """
    policy = load_clinical_query_policy(policy_path)
    known_groups = {group["group_id"] for group in groups}
    planned = {QueryRuleScope.model_validate(row["scope"]).key(): deepcopy(row) for row in catalog}
    if len(planned) != len(catalog):
        raise ValueError("Bundled query rules contain duplicate scopes")

    def destination(scope: QueryRuleScope) -> dict:
        """Return the release being assembled for a validated installation scope."""
        if scope.assay_group and scope.assay_group not in known_groups:
            raise ValueError(f"Query policy requires registered group: {scope.assay_group}")
        if scope.asp_id or scope.subpanel_id:
            raise ValueError(
                "Install assay/subpanel query rules through the editor after assay activation"
            )
        return planned.setdefault(
            scope.key(),
            {
                "scope": scope.model_dump(),
                "scope_key": scope.key(),
                "name": f"{scope.assay_group or 'Default'} {scope.analysis} {scope.intent} selection",
                "content": {"evidence_mode": None, "exceptions": []},
            },
        )

    for row in list(planned.values()):
        destination(QueryRuleScope.model_validate(row["scope"]))
    for group, mode in policy.snv.assay_group_policies.items():
        destination(QueryRuleScope(assay_group=group, analysis="snv"))["content"][
            "evidence_mode"
        ] = mode
    if policy.pgx.exceptions:
        raise ValueError("PGX query rules have no implemented retrieval namespace")
    for analysis in ("snv", "cnv", "translocation", "fusion"):
        for exception in getattr(policy, analysis).exceptions:
            intents = exception.intents or (
                ("somatic", "germline") if analysis == "snv" else ("somatic",)
            )
            for group, assay, panel, intent in product(
                exception.assay_groups or (None,),
                exception.asp_ids or (None,),
                exception.subpanel_ids or (None,),
                intents,
            ):
                row = destination(
                    QueryRuleScope(
                        assay_group=group,
                        asp_id=assay,
                        subpanel_id=panel,
                        analysis=analysis,
                        intent=intent,
                    )
                )
                rules = {entry["id"]: entry for entry in row["content"].get("exceptions") or []}
                rules[exception.rule_id] = exception_payload(exception)
                row["content"]["exceptions"] = list(rules.values())
    now = datetime.now(timezone.utc)
    result = []
    for row in sorted(planned.values(), key=lambda item: item["scope_key"]):
        scope = QueryRuleScope.model_validate(row["scope"])
        if scope.assay_group:
            parent = planned.get(QueryRuleScope(analysis=scope.analysis, intent=scope.intent).key())
            if parent:
                exceptions = {e["id"]: e for e in parent["content"]["exceptions"]}
                exceptions.update({e["id"]: e for e in row["content"].get("exceptions") or []})
                row["content"]["exceptions"] = list(exceptions.values())
        row.update(
            scope=scope.model_dump(),
            scope_key=scope.key(),
            query_id=scope.key(),
            name=scope.key(),
            version=1,
            revision=1,
            status="published",
            system_installed=True,
            reason="Installed query policy; validate before clinical use",
            created_by=actor,
            updated_by=actor,
            published_by=actor,
            approved_by=None,
            created_on=now,
            updated_on=now,
            published_on=now,
        )
        result.append(QueryRuleDoc.model_validate(row).model_dump(by_alias=True, exclude_none=True))
    return result
