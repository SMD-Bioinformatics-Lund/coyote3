"""Load the constrained, center-owned clinical SNV query policy.

The policy is deliberately declarative.  It selects one of the supported
baseline evidence models and defines narrowly typed clinical admission
exceptions.  It never exposes MongoDB operators or field paths to configuration
authors; those remain application-owned behavior in ``varqueries``.
"""

from __future__ import annotations

import re
import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from api.config.paths import CLINICAL_QUERY_POLICY_PATH

_POLICY_MODES = frozenset({"paired", "case_only", "exception_only"})
_EXCEPTION_MODES = frozenset({"extend_consequence", "admit", "exclude"})
_IDENTIFIER_RE = re.compile(r"^[A-Za-z0-9_-]+$")
_SNV_POLICY_KEYS = frozenset(
    {
        "default_somatic_policy",
        "default_germline_policy",
        "population_frequency_fields",
        "assay_group_policies",
        "exceptions",
    }
)
_EXCEPTION_KEYS = frozenset(
    {
        "id",
        "mode",
        "intents",
        "assay_groups",
        "asp_ids",
        "subpanel_ids",
        "genes",
        "consequence_terms",
        "filter_values",
        "chromosomes",
        "position_min",
        "position_max",
        "simple_ids",
        "info_fields_present",
        "info_equals",
        "alt_regex",
    }
)


def _strings(
    value: Any, *, key: str, uppercase: bool = False, lowercase: bool = True
) -> tuple[str, ...]:
    """Normalize an optional identifier list from the policy document."""
    if value is None:
        return ()
    if not isinstance(value, list):
        raise RuntimeError(f"clinical query policy key '{key}' must be an array")
    normalized = tuple(
        str(item or "").strip().upper()
        if uppercase
        else str(item or "").strip().lower()
        if lowercase
        else str(item or "").strip()
        for item in value
    )
    if any(not item for item in normalized) or len(set(normalized)) != len(normalized):
        raise RuntimeError(
            f"clinical query policy key '{key}' must contain unique non-empty values"
        )
    return normalized


def _identifiers(value: Any, *, key: str) -> tuple[str, ...]:
    """Return normalized clinical identifiers and reject unsupported characters."""
    values = _strings(value, key=key)
    invalid = [item for item in values if not _IDENTIFIER_RE.fullmatch(item)]
    if invalid:
        raise RuntimeError(
            f"clinical query policy key '{key}' contains invalid identifiers: {', '.join(invalid)}"
        )
    return values


def _case_preserving_identifiers(value: Any, *, key: str) -> tuple[str, ...]:
    """Validate field identifiers while preserving their stored VCF casing."""
    values = _strings(value, key=key, lowercase=False)
    invalid = [item for item in values if not _IDENTIFIER_RE.fullmatch(item)]
    if invalid:
        raise RuntimeError(
            f"clinical query policy key '{key}' contains invalid identifiers: {', '.join(invalid)}"
        )
    return values


@dataclass(frozen=True)
class SnvQueryException:
    """A scope-limited typed admission branch for the SNV query builder."""

    rule_id: str
    mode: str
    intents: tuple[str, ...]
    assay_groups: tuple[str, ...]
    asp_ids: tuple[str, ...]
    subpanel_ids: tuple[str, ...]
    genes: tuple[str, ...]
    consequence_terms: tuple[str, ...]
    filter_values: tuple[str, ...]
    chromosomes: tuple[str, ...]
    position_min: int | None
    position_max: int | None
    simple_ids: tuple[str, ...]
    info_fields_present: tuple[str, ...]
    info_equals: dict[str, Any]
    alt_regex: str | None

    def applies_to(self, *, assay_group: str, asp_id: str, subpanel_id: str, intent: str) -> bool:
        """Return whether this released exception applies to the request scope."""
        return (
            (not self.intents or intent in self.intents)
            and (not self.assay_groups or assay_group in self.assay_groups)
            and (not self.asp_ids or asp_id in self.asp_ids)
            and (not self.subpanel_ids or subpanel_id in self.subpanel_ids)
        )


@dataclass(frozen=True)
class SnvQueryPolicy:
    """Validated SNV query policy used by the domain query builder."""

    default_somatic_policy: str
    default_germline_policy: str
    assay_group_policies: dict[str, str]
    population_frequency_fields: tuple[str, ...]
    exceptions: tuple[SnvQueryException, ...]

    def policy_for(self, *, assay_group: str, intent: str) -> str:
        """Resolve the configured baseline policy for one analysis request."""
        if intent == "germline":
            return self.default_germline_policy
        return self.assay_group_policies.get(assay_group, self.default_somatic_policy)

    def exceptions_for(
        self, *, assay_group: str, asp_id: str, subpanel_id: str, intent: str, mode: str
    ) -> tuple[SnvQueryException, ...]:
        """Return matching exceptions in the configuration's display order.

        Query exceptions are additive Mongo ``$or`` branches. Their order does
        not convey clinical precedence and does not change the result set.
        TOML ordering is retained only to keep diagnostic output familiar to
        the configuration author.
        """
        return tuple(
            exception
            for exception in self.exceptions
            if exception.mode == mode
            and exception.applies_to(
                assay_group=assay_group,
                asp_id=asp_id,
                subpanel_id=subpanel_id,
                intent=intent,
            )
        )


def _policy_mode(value: Any, *, key: str) -> str:
    mode = str(value or "").strip().lower()
    if mode not in _POLICY_MODES:
        raise RuntimeError(
            f"clinical query policy key '{key}' must be one of: {', '.join(sorted(_POLICY_MODES))}"
        )
    return mode


def _exception(raw: Any, *, index: int) -> SnvQueryException:
    """Validate one declarative exception without accepting raw Mongo syntax."""
    if not isinstance(raw, dict):
        raise RuntimeError(f"snv.exceptions[{index}] must be a table")
    unexpected = set(raw) - _EXCEPTION_KEYS
    if unexpected:
        raise RuntimeError(
            f"snv.exceptions[{index}] contains unsupported key(s): {', '.join(sorted(unexpected))}"
        )
    rule_id = _identifiers([raw.get("id")], key=f"snv.exceptions[{index}].id")[0]
    mode = str(raw.get("mode") or "").strip().lower()
    if mode not in _EXCEPTION_MODES:
        raise RuntimeError(
            f"snv.exceptions[{index}].mode must be one of: {', '.join(sorted(_EXCEPTION_MODES))}"
        )
    intents = _identifiers(raw.get("intents"), key=f"snv.exceptions[{index}].intents")
    invalid_intents = set(intents) - {"somatic", "germline"}
    if invalid_intents:
        raise RuntimeError(f"snv.exceptions[{index}].intents contains unsupported values")
    info_equals = raw.get("info_equals") or {}
    if not isinstance(info_equals, dict) or any(
        not _IDENTIFIER_RE.fullmatch(str(key)) for key in info_equals
    ):
        raise RuntimeError(
            f"snv.exceptions[{index}].info_equals must map INFO identifiers to values"
        )
    position_min = raw.get("position_min")
    position_max = raw.get("position_max")
    try:
        if position_min is not None:
            position_min = int(position_min)
        if position_max is not None:
            position_max = int(position_max)
    except (TypeError, ValueError) as error:
        raise RuntimeError(f"snv.exceptions[{index}] position bounds must be integers") from error
    if position_min is not None and position_max is not None and position_min > position_max:
        raise RuntimeError(f"snv.exceptions[{index}] position_min must not exceed position_max")
    alt_regex = str(raw.get("alt_regex")).strip() if raw.get("alt_regex") else None
    if alt_regex:
        try:
            re.compile(alt_regex)
        except re.error as error:
            raise RuntimeError(f"snv.exceptions[{index}].alt_regex is invalid") from error
    result = SnvQueryException(
        rule_id=rule_id,
        mode=mode,
        intents=intents,
        assay_groups=_identifiers(
            raw.get("assay_groups"), key=f"snv.exceptions[{index}].assay_groups"
        ),
        asp_ids=_identifiers(raw.get("asp_ids"), key=f"snv.exceptions[{index}].asp_ids"),
        subpanel_ids=_identifiers(
            raw.get("subpanel_ids"), key=f"snv.exceptions[{index}].subpanel_ids"
        ),
        genes=_strings(raw.get("genes"), key=f"snv.exceptions[{index}].genes", uppercase=True),
        consequence_terms=_strings(
            raw.get("consequence_terms"),
            key=f"snv.exceptions[{index}].consequence_terms",
            lowercase=False,
        ),
        filter_values=_strings(
            raw.get("filter_values"), key=f"snv.exceptions[{index}].filter_values", uppercase=True
        ),
        chromosomes=_strings(
            raw.get("chromosomes"), key=f"snv.exceptions[{index}].chromosomes", uppercase=True
        ),
        position_min=position_min,
        position_max=position_max,
        simple_ids=_strings(
            raw.get("simple_ids"), key=f"snv.exceptions[{index}].simple_ids", lowercase=False
        ),
        info_fields_present=_case_preserving_identifiers(
            raw.get("info_fields_present"), key=f"snv.exceptions[{index}].info_fields_present"
        ),
        info_equals=dict(info_equals),
        alt_regex=alt_regex,
    )
    if not any(
        (
            result.genes,
            result.consequence_terms,
            result.filter_values,
            result.chromosomes,
            result.position_min is not None,
            result.position_max is not None,
            result.simple_ids,
            result.info_fields_present,
            result.info_equals,
            result.alt_regex,
        )
    ):
        raise RuntimeError(f"snv.exceptions[{index}] must define at least one match criterion")
    return result


def load_snv_query_policy(path: str | Path = CLINICAL_QUERY_POLICY_PATH) -> SnvQueryPolicy:
    """Load the center-owned, safe SNV query-policy configuration."""
    path_obj = Path(path)
    if not path_obj.exists():
        raise RuntimeError(f"clinical query policy configuration does not exist: {path_obj}")
    with path_obj.open("rb") as handle:
        raw = tomllib.load(handle)
    snv = raw.get("snv")
    if not isinstance(snv, dict):
        raise RuntimeError("clinical query policy requires an [snv] table")
    unexpected = set(snv) - _SNV_POLICY_KEYS
    if unexpected:
        raise RuntimeError("snv contains unsupported key(s): " + ", ".join(sorted(unexpected)))
    policies = snv.get("assay_group_policies") or {}
    if not isinstance(policies, dict):
        raise RuntimeError("snv.assay_group_policies must be a table")
    assay_group_policies = {
        _identifiers([key], key=f"snv.assay_group_policies.{key}")[0]: _policy_mode(
            value, key=f"snv.assay_group_policies.{key}"
        )
        for key, value in policies.items()
    }
    raw_exceptions = snv.get("exceptions") or []
    if not isinstance(raw_exceptions, list):
        raise RuntimeError("snv.exceptions must be an array of tables")
    exceptions = tuple(_exception(item, index=index) for index, item in enumerate(raw_exceptions))
    if len({item.rule_id for item in exceptions}) != len(exceptions):
        raise RuntimeError("snv.exceptions ids must be unique")
    return SnvQueryPolicy(
        default_somatic_policy=_policy_mode(
            snv.get("default_somatic_policy"), key="snv.default_somatic_policy"
        ),
        default_germline_policy=_policy_mode(
            snv.get("default_germline_policy"), key="snv.default_germline_policy"
        ),
        assay_group_policies=assay_group_policies,
        population_frequency_fields=_strings(
            snv.get("population_frequency_fields"),
            key="snv.population_frequency_fields",
            lowercase=False,
        ),
        exceptions=exceptions,
    )


SNV_QUERY_POLICY = load_snv_query_policy()
