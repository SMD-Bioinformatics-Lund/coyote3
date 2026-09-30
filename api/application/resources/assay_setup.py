"""Draft-first assay setup using the existing ASPC and gene-list validators."""

import json
from copy import deepcopy
from datetime import datetime, timezone
from hashlib import sha256
from typing import Any

from pydantic import ValidationError

from api.application.accounts.common import build_managed_form
from api.application.reporting.clinical_rules.resolution import resolve_published_rule_set
from api.application.resources.aspc import AspcService
from api.application.resources.helpers import require_new_identifier
from api.application.resources.isgl import IsglService
from api.config.constants import ENVIRONMENT_OPTIONS
from api.contracts.managed_resources import managed_resource_spec
from api.contracts.schemas.assay import InsilicoGenelistsDoc
from api.contracts.schemas.assay_setup import AssaySetupContent, AssaySetupDoc
from api.domain.common.errors import api_error
from api.domain.core.exceptions import AppError


class SetupWorkspace:
    """In-memory repository interfaces for validating and previewing staged resources.

    Notes:
        These methods never write operational collections. Existing resource services
        perform their normal validation against this explicitly selected workspace.
    """

    def __init__(self, content: AssaySetupContent, store: Any, actor: str) -> None:
        """Bind a draft's assay and scopes, retaining live sources for reference choices."""
        self.store = store
        self.actor = actor
        if content.panel.asp_group not in self.group_options():
            raise api_error(422, "Register the assay group before configuring the assay")
        self.now = datetime.now(timezone.utc)
        self.panel = self.document(
            content.panel.model_dump(by_alias=True, exclude_computed_fields=True)
        )
        self.definitions = [
            d
            for d in store.assay_subpanel_repository.list_definitions()
            if d["subpanel_id"] in content.scopes
        ]
        if set(content.scopes) - {"base"} != {
            d["subpanel_id"] for d in self.definitions if d["is_active"]
        }:
            raise api_error(422, "Select available subpanel definitions; Base is implicit")
        self.gene_lists: list[dict] = []
        self.configurations: list[dict] = []
        self.existing_lists = list(
            store.gene_list_repository.get_isgl_for_scope(
                asp_name=self.panel["asp_id"],
                assay_group=self.panel["asp_group"],
                is_active=True,
                adhoc=False,
            )
            or []
        )

    def document(self, source: dict) -> dict:
        """Remove imported persistence identity and assign authoritative creation metadata."""
        doc = {
            k: deepcopy(v)
            for k, v in source.items()
            if k not in {"_id", "supersedes_id", "retired_by", "retired_on", "retired_reason"}
        }
        doc.update(
            is_active=True,
            system_managed=False,
            version=1,
            created_by=self.actor,
            updated_by=self.actor,
            created_on=self.now,
            updated_on=self.now,
        )
        return doc

    def get_asp(self, identifier: str) -> dict | None:
        """Resolve only the draft's assay identity."""
        return self.panel if identifier == self.panel["asp_id"] else None

    def get_all_asps(self, *, is_active: bool = True) -> list[dict]:
        """Supply the staged assay to managed-form scope choices."""
        return [self.panel] if is_active else []

    def list_for_assay(self, identifier: str, *, active_only: bool = False) -> list[dict]:
        """Return selected named scopes without creating association records."""
        return self.definitions if identifier == self.panel["asp_id"] else []

    def get_isgl(self, identifier: str) -> dict | None:
        """Check staged and existing gene-list identities for collisions."""
        return next(
            (g for g in self.gene_lists if g["isgl_id"] == identifier), None
        ) or self.store.gene_list_repository.get_isgl(identifier)

    def create_genelist(self, document: dict) -> None:
        """Stage a validated gene list rather than persisting it."""
        self.gene_lists.append(self.document(document))

    def get_isgl_for_scope(self, **_kwargs: Any) -> list[dict]:
        """Combine active shared lists and validated staged lists for filter choices."""
        return self.existing_lists + [g for g in self.gene_lists if not g.get("adhoc")]

    def build_aspc_id(self, *args: Any) -> str:
        """Use the canonical ASPC identity builder."""
        return self.store.assay_configuration_repository.build_aspc_id(*args)

    def get_aspc_with_id(self, identifier: str) -> dict | None:
        """Check staged and operational ASPC identities before adding a configuration."""
        return next(
            (c for c in self.configurations if c["aspc_id"] == identifier), None
        ) or self.store.assay_configuration_repository.get_aspc_with_id(identifier)

    def create_assay_config(self, document: dict) -> None:
        """Stage a validated ASPC without exposing it to ingest."""
        self.configurations.append(self.document(document))

    def group_options(self) -> list[str]:
        """Use the live registry for draft form options and group validation."""
        return self.store.assay_panel_repository.group_options()

    def services(self, common_util: Any) -> tuple[IsglService, AspcService]:
        """Build existing resource validators against this draft workspace."""
        return IsglService(
            gene_list_repository=self, assay_panel_repository=self, assay_subpanel_repository=self
        ), AspcService(
            assay_configuration_repository=self,
            assay_panel_repository=self,
            assay_subpanel_repository=self,
            gene_list_repository=self,
            vep_metadata_repository=self.store.vep_metadata_repository,
            clinical_rule_set_repository=self.store.clinical_rule_set_repository,
            common_util=common_util,
        )


class AssaySetupService:
    """Manage resumable drafts, readiness, independent review and atomic activation."""

    def __init__(self, store: Any, *, common_util: Any) -> None:
        """Bind application repositories and managed-form helpers."""
        self.store = store
        self.repository = store.assay_setup_repository
        self.common_util = common_util

    def get(self, identifier: str) -> dict:
        """Load a saved setup or return a not-found error."""
        document = self.repository.get(identifier)
        if not document:
            raise api_error(404, "Assay setup not found")
        return document

    def list_payload(self) -> dict:
        """Return setup summaries without embedding their configuration content."""
        return {"items": self.repository.list()}

    def save(
        self,
        content: AssaySetupContent,
        *,
        actor: str,
        identifier: str | None = None,
        revision: int | None = None,
    ) -> dict:
        """Create or revise a draft; operational assay resources remain untouched."""
        previous = self.get(identifier) if identifier else None
        if previous is None:
            require_new_identifier(content.panel.asp_id, label="asp_id")
        if previous and (previous["status"] != "draft" or previous["revision"] != revision):
            raise api_error(409, "Only the current draft revision can be edited")
        if previous and previous["asp_id"] != content.panel.asp_id:
            raise api_error(422, "The reserved assay identifier cannot be changed")
        # Validate scope availability even when later configuration steps are incomplete.
        SetupWorkspace(content, self.store, actor)
        now = datetime.now(timezone.utc)
        values = {
            **(previous or {}),
            "asp_id": content.panel.asp_id,
            "content": content.model_dump(exclude_computed_fields=True),
            "revision": (previous["revision"] + 1) if previous else 1,
            "status": "draft",
            "created_by": previous["created_by"] if previous else actor,
            "created_at": previous["created_at"] if previous else now,
            "updated_by": actor,
            "updated_at": now,
            "content_editors": list(
                dict.fromkeys([*(previous or {}).get("content_editors", []), actor])
            ),
        }
        payload = AssaySetupDoc.model_validate(values).model_dump(
            by_alias=True, exclude_computed_fields=True
        )
        return self.repository.save(
            payload, previous=previous, action="saved" if previous else "created"
        )

    def _workspace(self, document: dict, actor: str) -> SetupWorkspace:
        """Validate staged lists using the normal gene-list service."""
        content = AssaySetupContent.model_validate(document["content"])
        workspace = SetupWorkspace(content, self.store, actor)
        lists, _ = workspace.services(self.common_util)
        for config in content.gene_lists:
            values = workspace.document(config)
            values["asp_ids"] = [content.panel.asp_id]
            values["asp_groups"] = [content.panel.asp_group]
            lists.create(payload={"config": values}, actor_username=actor)
            if set(workspace.gene_lists[-1].get("diagnosis") or []) - set(content.scopes):
                raise api_error(422, "Gene-list diagnoses must be selected setup scopes")
        return workspace

    def context(self, identifier: str | None, *, actor: str) -> dict:
        """Return managed forms, scope choices, rule references and saved progress."""
        result = {
            "panel_form": build_managed_form(managed_resource_spec("asp"), actor_username=actor),
            "subpanels": self.store.assay_subpanel_repository.list_definitions(),
            "environments": list(ENVIRONMENT_OPTIONS),
        }
        result["panel_form"]["fields"]["asp_group"]["options"] = (
            self.store.assay_panel_repository.group_options()
        )
        if not identifier:
            return result
        doc = self.get(identifier)
        result["setup"] = doc
        result["history"] = [
            {
                "revision": r["revision"],
                "action": r["action"],
                "actor": r["document"]["updated_by"],
                "at": r["document"]["updated_at"],
            }
            for r in self.repository.revisions(identifier)
        ]
        try:
            workspace = SetupWorkspace(
                AssaySetupContent.model_validate(doc["content"]), self.store, actor
            )
            lists, configs = workspace.services(self.common_util)
            result["genelist_form"] = lists.create_context_payload(actor_username=actor)["form"]
            for source in doc["content"]["gene_lists"]:
                try:
                    values = workspace.document(source)
                    values.update(
                        asp_ids=[workspace.panel["asp_id"]],
                        asp_groups=[workspace.panel["asp_group"]],
                    )
                    if doc["status"] == "published":
                        workspace.gene_lists.append(
                            InsilicoGenelistsDoc.model_validate(values).model_dump(
                                exclude_computed_fields=True
                            )
                        )
                    else:
                        lists.create(payload={"config": values}, actor_username=actor)
                except (AppError, ValidationError, ValueError) as exc:
                    result["context_error"] = str(exc)
            result["configuration_form"] = configs.create_context_payload(
                category=workspace.panel["asp_category"], actor_username=actor
            )["form"]
            result["configuration_form"]["fields"]["environment"]["options"] = doc["content"][
                "environments"
            ]
        except (AppError, ValidationError) as exc:
            result["context_error"] = str(exc)
        result["rules"] = self.store.clinical_rule_set_repository.list_active_for_assay(
            doc["asp_id"]
        )
        result["readiness"] = (
            {"ready": True, "issues": []}
            if doc["status"] == "published"
            else self.readiness(doc, actor=actor)
        )
        return result

    def bundle(self, document: dict, *, actor: str) -> dict:
        """Validate every selected scope/environment and prepare operational documents.

        Raises:
            AppError: Configuration is incomplete, references an unavailable rule,
                duplicates an identity or includes an unselected scope/environment.
        """
        content = AssaySetupContent.model_validate(document["content"])
        if not content.environments:
            raise api_error(422, "Select at least one environment")
        workspace = self._workspace(document, actor)
        _, configs = workspace.services(self.common_util)
        expected = {(scope, env) for scope in content.scopes for env in content.environments}
        actual = set()
        rules = {}
        for source in content.configurations:
            config = workspace.document(source)
            config["asp_id"] = content.panel.asp_id
            key = (config.get("subpanel_id") or "base", config.get("environment"))
            if key not in expected or key in actual:
                raise api_error(422, "Each selected scope/environment needs exactly one ASPC")
            configs.create(payload={"config": config}, actor_username=actor)
            actual.add(key)
            reporting = workspace.configurations[-1]["reporting"]
            try:
                rule = resolve_published_rule_set(
                    self.store.clinical_rule_set_repository,
                    asp_id=content.panel.asp_id,
                    subpanel_id=key[0],
                    analyte=config["asp_category"].lower(),
                    language=reporting.get("language", "sv"),
                )
            except ValueError as exc:
                raise api_error(409, str(exc)) from exc
            rules[rule.rule_set_id] = rule.model_dump(mode="python", by_alias=True)
        missing = expected - actual
        if missing:
            raise api_error(
                422, "Missing ASPCs: " + ", ".join(f"{s}/{e}" for s, e in sorted(missing))
            )
        return {
            "panel": workspace.panel,
            "gene_lists": workspace.gene_lists,
            "configurations": workspace.configurations,
            "rules": list(rules.values()),
            "definitions": workspace.definitions,
            "existing_lists": workspace.existing_lists,
            "associations": [
                {
                    "asp_id": content.panel.asp_id,
                    "subpanel_id": d["subpanel_id"],
                    "is_active": True,
                    "is_current": True,
                    "version": 1,
                    "updated_by": actor,
                    "updated_on": workspace.now,
                }
                for d in workspace.definitions
            ],
        }

    def readiness(self, document: dict, *, actor: str) -> dict:
        """Return actionable validation feedback without changing setup or sample data."""
        try:
            self.bundle(document, actor=actor)
            return {"ready": True, "issues": []}
        except (AppError, ValidationError, ValueError) as exc:
            return {"ready": False, "issues": [str(exc)]}

    @staticmethod
    def dependency_hash(bundle: dict) -> str:
        """Pin reviewed live dependencies so changes require another review submission."""
        identities = [
            (kind, str(d.get("_id")), d.get("version"), d.get("revision"))
            for kind in ("rules", "definitions", "existing_lists")
            for d in bundle[kind]
        ]
        return sha256(json.dumps(sorted(identities), default=str).encode()).hexdigest()

    def transition(
        self, identifier: str, revision: int, action: str, *, actor: str, reason: str = ""
    ) -> dict:
        """Submit, return for correction, or independently approve and activate a setup."""
        previous = self.get(identifier)
        required = "draft" if action == "submit" else "submitted"
        if (
            action not in {"submit", "return", "publish"}
            or previous["status"] != required
            or previous["revision"] != revision
        ):
            raise api_error(409, "The setup state or revision does not allow this operation")
        if action in {"publish", "return"} and actor in previous["content_editors"]:
            raise api_error(403, "An independent reviewer must approve or return the setup")
        if action == "return" and not reason.strip():
            raise api_error(422, "Explain which changes are required")
        bundle = self.bundle(previous, actor=actor) if action != "return" else None
        digest = self.dependency_hash(bundle) if bundle else None
        if action == "publish" and digest != previous.get("review_dependencies"):
            raise api_error(
                409, "Setup dependencies changed after submission; return it for a new review"
            )
        values = {
            **previous,
            "revision": revision + 1,
            "updated_by": actor,
            "updated_at": datetime.now(timezone.utc),
            "review_reason": reason,
            "status": {"submit": "submitted", "return": "draft", "publish": "published"}[action],
            "review_dependencies": digest,
        }
        if action == "publish":
            values["published_by"] = actor
        return self.repository.save(
            values, previous=previous, action=action, bundle=bundle if action == "publish" else None
        )
