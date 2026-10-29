"""Validate reusable profiles and compile deterministic configuration values with provenance."""

import json
from copy import deepcopy
from datetime import datetime, timezone
from hashlib import sha256
from typing import Any

from coyote3.application.common.protected_records import reject_system_managed_change
from coyote3.application.reporting.clinical_rules.validation import content_hash, validate_rule_set
from coyote3.application.reporting.report_renderer import template_content_hash
from coyote3.application.reporting.report_service import REPORT_TEMPLATES
from coyote3.contracts.configuration_profiles import ConfigurationProfileDraft, ConfigurationScope
from coyote3.contracts.schemas.assay import AspcReportingDoc
from coyote3.contracts.schemas.clinical_rules import (
    ClinicalRuleBlock,
    ClinicalRuleSetDoc,
    ClinicalRuleTestCase,
)
from coyote3.contracts.schemas.filter_profiles import DnaFilterProfilesDoc, RnaFilterProfilesDoc
from coyote3.domain.common.errors import api_error


def profile_hash(document: dict) -> str:
    """Hash profile identity, kind, content and bindings, excluding publication metadata."""
    content = {key: document[key] for key in ("profile_id", "kind", "bindings", "content")}
    return sha256(json.dumps(content, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def merge_profile_values(base: dict, overrides: dict) -> dict:
    """Merge explicit fields recursively; lists, null and empty values replace rather than inherit."""
    result = deepcopy(base)
    for key, value in overrides.items():
        if isinstance(value, dict) and isinstance(result.get(key), dict):
            result[key] = merge_profile_values(result[key], value)
        else:
            result[key] = deepcopy(value)
    return result


def changed_profile_values(previous: dict, submitted: dict) -> dict:
    """Extract explicitly changed fields from an edited compiled component.

    Args:
        previous: Previously compiled values shown in the configuration editor.
        submitted: Edited component; absent fields are not submitted overrides.

    Returns:
        Changed fields only, preserving explicit empty lists and null values.
    """
    changes = {}
    for key, value in submitted.items():
        if key in previous and previous[key] == value:
            continue
        if isinstance(value, dict) and isinstance(previous.get(key), dict):
            nested = changed_profile_values(previous[key], value)
            if nested:
                changes[key] = nested
        else:
            changes[key] = deepcopy(value)
    return changes


def prepare_profile_update(previous: dict, submitted: dict, updated: dict) -> None:
    """Restore explicit inputs before compiling the next configuration revision.

    Args:
        previous: Stored release containing compiled values and authored overrides.
        submitted: Editor payload, which may contain unchanged compiled values.
        updated: Mutable candidate receiving only authored component inputs.
    """
    overrides = deepcopy(previous.get("profile_overrides") or {})
    for kind in ("filters", "reporting"):
        if not previous.get("profile_sources"):
            overrides[kind] = deepcopy(previous.get(kind) or {})
        if kind in submitted:
            overrides[kind] = merge_profile_values(
                overrides.get(kind, {}),
                changed_profile_values(previous.get(kind) or {}, submitted[kind] or {}),
            )
        updated[kind] = overrides.get(kind, {})


def validate_profile_content(draft: ConfigurationProfileDraft) -> None:
    """Reject unsupported filter keys, report settings and unregistered template layouts.

    Args:
        draft: Proposed immutable source profile.

    Raises:
        ValueError: Content does not match its selected component contract.
    """
    if draft.kind == "filters":
        errors = []
        for model in (DnaFilterProfilesDoc, RnaFilterProfilesDoc):
            try:
                model.model_validate(draft.content)
                return
            except ValueError as error:
                errors.append(str(error))
        raise ValueError("Invalid DNA/RNA filter profile: " + "; ".join(errors))
    if draft.kind == "reporting":
        # Partial fields are reusable overrides. Validate values using a complete
        # synthetic baseline; compilation validates the final operational document.
        baseline = {
            "report_header": "Profile validation",
            "report_method": "Profile validation",
            "plots_path": "plots",
            "report_folder": "reports",
        }
        AspcReportingDoc.model_validate({**baseline, **draft.content})
        return
    if draft.kind == "clinical_rules":
        if set(draft.content) - {"replace_blocks", "disable_blocks", "replace_tests"}:
            raise ValueError(
                "Rule profiles accept replace_blocks, disable_blocks and replace_tests"
            )
        blocks = [
            ClinicalRuleBlock.model_validate(row) for row in draft.content.get("replace_blocks", [])
        ]
        identifiers = [block.block_id for block in blocks]
        disabled = draft.content.get("disable_blocks", [])
        if not isinstance(disabled, list) or any(not isinstance(value, str) for value in disabled):
            raise ValueError("disable_blocks must be a list of block identifiers")
        if len(identifiers) != len(set(identifiers)) or set(identifiers).intersection(disabled):
            raise ValueError("A rule block may have only one operation per profile")
        tests = [
            ClinicalRuleTestCase.model_validate(row)
            for row in draft.content.get("replace_tests", [])
        ]
        if len({test.test_id for test in tests}) != len(tests):
            raise ValueError("A rule test may have only one replacement per profile")
        return
    if set(draft.content) - {"template_name", "content_hash"}:
        raise ValueError("Template profiles accept template_name and content_hash")
    name = draft.content.get("template_name")
    if name not in REPORT_TEMPLATES:
        raise ValueError("Choose a registered report template")
    draft.content.setdefault("content_hash", template_content_hash(name))
    if draft.content["content_hash"] != template_content_hash(name):
        raise ValueError("Template hash does not identify the installed layout revision")


class ConfigurationProfileService:
    """Create immutable drafts and require a distinct reviewer for publication."""

    def __init__(self, repository: Any):
        """Bind profile persistence on the application database."""
        self.repository = repository

    def list(self) -> list[dict]:
        """List retained source profile revisions for the authoring workspace."""
        return self.repository.list()

    def create(self, draft: ConfigurationProfileDraft, *, actor: str) -> dict:
        """Validate content and save the next immutable draft revision."""
        for scope in draft.bindings:
            resources = self.repository.scope_resources(scope)
            if scope.asp_group and not (resources["group"] or {}).get("is_active"):
                raise api_error(422, "Select an active registered biological group")
            if scope.asp_id and (resources["assay"] or {}).get("asp_group") != scope.asp_group:
                raise api_error(422, "The registered assay does not belong to the selected group")
            if scope.diagnosis_id and not (resources["diagnosis"] or {}).get("is_active"):
                raise api_error(422, "Select an active registered diagnosis")
        try:
            validate_profile_content(draft)
        except ValueError as error:
            raise api_error(422, str(error)) from error
        document = draft.model_dump(mode="json")
        document.update(
            created_by=actor,
            updated_by=actor,
            created_on=datetime.now(timezone.utc),
            content_hash=profile_hash(document),
            status="draft",
            is_current=False,
            published_by=None,
            published_on=None,
        )
        return self.repository.create(document)

    def publish(self, identity: str, *, actor: str, content_hash: str, reason: str) -> dict:
        """Publish only the exact reviewed draft with an author-independent approval."""
        document = self.repository.get(identity)
        if not document:
            raise api_error(404, "Configuration profile not found")
        reject_system_managed_change(document, resource="configuration profile")
        if document["created_by"] == actor:
            raise api_error(403, "Another authorized user must review this profile")
        if document["status"] != "draft" or document["content_hash"] != content_hash:
            raise api_error(409, "Review the current draft content before publishing")
        if profile_hash(document) != content_hash:
            raise api_error(409, "Profile content failed integrity validation")
        try:
            validate_profile_content(
                ConfigurationProfileDraft.model_validate(
                    {key: document[key] for key in ConfigurationProfileDraft.model_fields}
                )
            )
        except ValueError as error:
            raise api_error(422, str(error)) from error
        return self.repository.publish(document, actor=actor, reason=reason)


def compile_profiles(
    configuration: dict, panel: dict, repository: Any, *, kinds: set[str] | None = None
) -> None:
    """Compile published scoped defaults before explicit configuration overrides.

    Args:
        configuration: Mutable configuration before full-schema validation.
        panel: Registered assay defining group, modality and family.
        repository: Published profile source; None means no configured reusable defaults.
        kinds: Components to resolve; None captures settings and templates, excluding clinical rules.

    Raises:
        AppError: A binding is ambiguous or published source content fails integrity checks.
    """
    selected = {}
    kinds = {"filters", "reporting", "template"} if kinds is None else kinds
    configuration["template_release"] = None
    for document in repository.published() if repository is not None else []:
        if document["kind"] not in kinds:
            continue
        if profile_hash(document) != document["content_hash"]:
            raise api_error(422, "Configuration profile failed integrity validation")
        for binding in document["bindings"]:
            scope = ConfigurationScope.model_validate(binding)
            if not scope.matches(configuration, panel):
                continue
            key = (*scope.rank(), document["kind"])
            if key in selected and selected[key]["_id"] != document["_id"]:
                raise api_error(422, "Multiple configuration profiles occupy the same binding rank")
            selected[key] = document
    defaults = {"filters": {}, "reporting": {}}
    configuration["profile_overrides"] = {
        kind: deepcopy(configuration.get(kind) or {}) for kind in defaults
    }
    sources = []
    for key, document in sorted(selected.items()):
        kind = document["kind"]
        if kind == "template":
            selected = REPORT_TEMPLATES[document["content"]["template_name"]]
            if selected[0] != panel["asp_category"]:
                raise api_error(422, "The report template does not support this assay modality")
            configuration["template_release"] = deepcopy(document["content"])
        elif kind != "clinical_rules":
            defaults[kind] = merge_profile_values(defaults[kind], document["content"])
        sources.append(
            {
                "profile_id": document["profile_id"],
                "version": document["version"],
                "document_id": str(document["_id"]),
                "content_hash": document["content_hash"],
                "rank": list(key[:2]),
                "kind": kind,
                "content": deepcopy(document["content"]),
            }
        )
    for kind, values in defaults.items():
        configuration[kind] = merge_profile_values(values, configuration.get(kind) or {})
    configuration["profile_sources"] = sources


def compile_profile_rules(configuration: dict) -> None:
    """Apply reviewed, explicit block replacements to the captured published rule source.

    Args:
        configuration: Mutable release containing its base rule artifact and ordered profile sources.

    Raises:
        AppError: A selected block does not exist, the compiled rules are invalid, or rules are absent.
    """
    sources = [
        source
        for source in configuration.get("profile_sources", [])
        if source["kind"] == "clinical_rules"
    ]
    configuration["clinical_rule_base"] = None
    if not sources:
        return
    base = configuration.get("clinical_rule_release")
    if not base:
        raise api_error(422, "Rule profiles require a published exact-context base rule release")
    configuration["clinical_rule_base"] = deepcopy(base)
    compiled = deepcopy(base)
    for source in sources:
        blocks = {block["block_id"]: block for block in compiled["blocks"]}
        for identity in source["content"].get("disable_blocks", []):
            if identity not in blocks:
                raise api_error(422, "A rule profile disables an unknown block")
            blocks.pop(identity)
        for replacement in source["content"].get("replace_blocks", []):
            if replacement["block_id"] not in blocks:
                raise api_error(422, "A rule profile replaces an unknown block")
            blocks[replacement["block_id"]] = deepcopy(replacement)
        compiled["blocks"] = list(blocks.values())
        tests = {test["test_id"]: test for test in compiled.get("test_cases", [])}
        for replacement in source["content"].get("replace_tests", []):
            if replacement["test_id"] not in tests:
                raise api_error(422, "A rule profile replaces an unknown test")
            tests[replacement["test_id"]] = deepcopy(replacement)
        compiled["test_cases"] = list(tests.values())
    try:
        document = ClinicalRuleSetDoc.model_validate(compiled)
        validation = validate_rule_set(document)
        if not validation.valid:
            raise ValueError("; ".join(validation.errors))
        document.content_hash = content_hash(document)
    except ValueError as error:
        raise api_error(422, "Compiled rule profiles failed validation", str(error)) from error
    configuration["clinical_rule_release"] = document.model_dump(mode="python", by_alias=True)
