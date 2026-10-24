"""Compile and verify immutable finding-selection policies in configuration releases."""

import hashlib
import json
from hmac import compare_digest
from typing import Any

from api.config.clinical_query_policy import (
    FindingQueryPolicy,
    SnvQueryPolicy,
    resolved_query_policy,
)
from api.contracts.schemas.query_rules import CompiledQueryPoliciesDoc, QueryRuleScope
from api.domain.common.errors import setup_error
from api.domain.common.sample_filters import normalize_analysis_intents


def query_policies_hash(policies: dict[str, Any]) -> str:
    """Hash canonical effective policy content and its exact source lineage.

    Args:
        policies: JSON-compatible resolution documents keyed by intent and analysis.

    Returns:
        SHA-256 digest independent of dictionary insertion order.
    """
    return hashlib.sha256(
        json.dumps(policies, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    ).hexdigest()


def compile_query_policies(
    configuration: dict[str, Any], panel: dict[str, Any], service: Any
) -> dict[str, Any]:
    """Resolve each enabled finding target once when preparing an ASPC revision.

    Args:
        configuration: Validated configuration scope, capabilities and intents.
        panel: Exact assay revision selected by the configuration author.
        service: Query-rule resolver over the reviewed source policies.

    Returns:
        Validated artifact containing effective policies, lineage and content hash.
    """
    policies = {}
    for analysis in configuration["analysis_types"]:
        analysis = analysis.lower()
        if analysis not in {"snv", "cnv", "translocation", "fusion"}:
            continue
        intents = (
            normalize_analysis_intents(
                configuration.get("analysis_intents"), asp_category=panel["asp_category"]
            )
            if analysis == "snv"
            else ["somatic"]
        )
        for intent in intents:
            scope = QueryRuleScope(
                assay_group=configuration["asp_group"],
                asp_id=configuration["asp_id"],
                diagnosis_id=configuration["diagnosis_id"],
                environment=configuration["environment"],
                modality=panel["asp_category"],
                family=panel["asp_family"],
                analysis=analysis,
                intent=intent,
            )
            policies[f"{intent}.{analysis}"] = service.resolve(scope).model_dump(mode="json")
    return CompiledQueryPoliciesDoc(
        policies=policies, content_hash=query_policies_hash(policies)
    ).model_dump(mode="json")


def load_compiled_query_policy(
    configuration: dict[str, Any], sample: dict[str, Any], analysis: str, intent: str
) -> SnvQueryPolicy | FindingQueryPolicy:
    """Read the pinned policy without consulting current rules or current assay metadata.

    Args:
        configuration: Exact ASPC revision referenced by the sample.
        sample: Sample identity and environment used to validate the release boundary.
        analysis: Finding namespace to query.
        intent: Independent analytical intent within that namespace.

    Returns:
        Typed query policy accepted by the domain query builders.

    Raises:
        AppError: Artifact is missing, tampered with, out of scope or lacks the target.
        ValueError: Stored policy violates its typed contract.
    """
    raw = configuration.get("query_policy_release")
    if not isinstance(raw, dict):
        raise setup_error("The sample configuration has no compiled query-policy release")
    release = CompiledQueryPoliciesDoc.model_validate(raw)
    policies = {key: value.model_dump(mode="json") for key, value in release.policies.items()}
    if not compare_digest(release.content_hash, query_policies_hash(policies)):
        raise setup_error("Compiled query-policy release failed its integrity check")
    policy = release.policies.get(f"{intent}.{analysis}")
    if policy is None:
        raise setup_error("The sample configuration does not enable this query target and intent")
    if (
        policy.scope.asp_id != sample.get("asp_id")
        or policy.scope.environment != sample.get("environment")
        or policy.scope.asp_id != configuration.get("asp_id")
        or policy.scope.environment != configuration.get("environment")
        or (policy.scope.diagnosis_id or "base") != configuration.get("diagnosis_id")
        or policy.scope.assay_group != configuration.get("asp_group")
        or policy.scope.analysis != analysis
        or policy.scope.intent != intent
    ):
        raise setup_error("Compiled query-policy scope does not match the sample configuration")
    return resolved_query_policy(analysis, policy.evidence_mode, policy.exceptions)
