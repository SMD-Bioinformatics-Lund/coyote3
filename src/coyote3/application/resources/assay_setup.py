"""Draft-first assay setup using the existing ASPC and gene-list validators."""

import json
from copy import deepcopy
from datetime import datetime, timezone
from hashlib import sha256
from typing import Any

from pydantic import ValidationError

from coyote3.application.accounts.common import build_managed_form
from coyote3.application.common.protected_records import reject_system_managed_change
from coyote3.application.reporting.clinical_rules.resolution import (
    MISSING_REPORTING_RULES_WARNING,
    MissingClinicalRuleSet,
    resolve_published_rule_set,
)
from coyote3.application.resources.aspc import AspcService
from coyote3.application.resources.helpers import require_new_identifier
from coyote3.application.resources.isgl import IsglService
from coyote3.config.constants import ENVIRONMENT_OPTIONS
from coyote3.contracts.authoring.resources import managed_resource_spec
from coyote3.contracts.schemas.assay import InsilicoGenelistsDoc
from coyote3.contracts.schemas.assay_setup import AssaySetupContent, AssaySetupDoc
from coyote3.domain.common.configuration_transfer import configuration_content
from coyote3.domain.common.errors import api_error
from coyote3.domain.exceptions import AppError


class SetupWorkspace:
    """In-memory repository interfaces for validating and previewing staged resources.

    Notes:
        These methods never write operational collections. Existing resource services
        perform their normal validation against this explicitly selected workspace.
    """

    def __init__(
        self,
        content: AssaySetupContent,
        store: Any,
        actor: str,
        *,
        created_at: datetime | None = None,
    ) -> None:
        """Bind draft resources with stable attribution for reproducible compilation.

        Args:
            content: Saved resource definitions or an unsaved form preview.
            store: Repositories used to validate shared resource references.
            actor: Draft creator retained in compiled resource attribution.
            created_at: Saved draft creation time; None uses now for unsaved previews.
        """
        self.store = store
        self.actor = actor
        if content.panel.asp_group not in self.group_options():
            raise api_error(422, "Register the assay group before configuring the assay")
        self.now = created_at if created_at is not None else datetime.now(timezone.utc)
        self.panel = self.document(
            content.panel.model_dump(by_alias=True, exclude_computed_fields=True)
        )
        self.definitions = [
            d
            for d in store.assay_diagnosis_repository.list_definitions()
            if d["diagnosis_id"] in content.scopes
        ]
        if set(content.scopes) - {"base"} != {
            d["diagnosis_id"] for d in self.definitions if d["is_active"]
        }:
            raise api_error(422, "Select available diagnosis definitions; Base is implicit")
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
        self.linked_lists: list[dict] = []
        for identifier in dict.fromkeys(content.existing_gene_list_ids):
            source = store.gene_list_repository.get_isgl(identifier)
            if not source or not source.get("is_active"):
                raise api_error(422, f"Gene list is unavailable: {identifier}")
            if self.panel["asp_id"] in (source.get("asp_ids") or []):
                continue
            reject_system_managed_change(source, resource="gene list")
            if set(source.get("diagnosis") or []) - set(content.scopes):
                raise api_error(422, f"Select the diagnoses required by gene list: {identifier}")
            linked = deepcopy(source)
            linked.pop("_id", None)
            linked.pop("gene_count", None)
            linked.update(
                asp_ids=list(dict.fromkeys([*(source.get("asp_ids") or []), self.panel["asp_id"]])),
                asp_groups=list(
                    dict.fromkeys([*(source.get("asp_groups") or []), self.panel["asp_group"]])
                ),
                version=int(source.get("version") or 1) + 1,
                supersedes_id=source["_id"],
                updated_by=actor,
                updated_on=self.now,
            )
            linked = InsilicoGenelistsDoc.model_validate(linked).model_dump(
                by_alias=True, exclude_computed_fields=True
            )
            linked.pop("_id", None)
            self.linked_lists.append(linked)
            if not any(g["_id"] == source["_id"] for g in self.existing_lists):
                self.existing_lists.append(source)

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
            system_installed=False,
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
        replacements = {g["isgl_id"]: g for g in self.linked_lists}
        return [
            replacements.get(g["isgl_id"], g) for g in self.existing_lists if not g.get("adhoc")
        ] + [g for g in self.gene_lists if not g.get("adhoc")]

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
            gene_list_repository=self, assay_panel_repository=self, assay_diagnosis_repository=self
        ), AspcService(
            assay_configuration_repository=self,
            assay_panel_repository=self,
            assay_diagnosis_repository=self,
            gene_list_repository=self,
            vep_metadata_repository=self.store.vep_metadata_repository,
            configuration_profile_repository=self.store.configuration_profile_repository,
        )


class AssaySetupService:
    """Manage resumable drafts, readiness, optional review and atomic activation."""

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

    def delete_unpublished(self, identifier: str, revision: int, *, actor: str) -> dict:
        """Discard a draft or submitted setup without deleting operational assay records.

        Args:
            identifier: Saved workspace identifier.
            revision: Expected current revision.
            actor: Authorized operator recorded in the deletion audit.

        Returns:
            Deleted workspace.

        Raises:
            AppError: The workspace is missing, changed, or already published.
        """
        deleted = self.repository.delete_unpublished(identifier, revision, actor)
        if deleted is None:
            raise api_error(409, "Only an unchanged unpublished assay setup can be deleted")
        return deleted

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
        """Create or revise a draft, replacing imported provenance at the write boundary.

        Args:
            content: Authored assay and staged configuration; audit fields are discarded.
            actor: Authenticated author recorded on the saved revision.
            identifier: Existing workspace identity, or None to reserve a new assay.
            revision: Expected revision for edits; unused when creating a workspace.

        Returns:
            Saved draft without writing operational assay resources.

        Raises:
            AppError: The state, revision, identifier or selected scopes prevent saving.
        """
        previous = self.get(identifier) if identifier else None
        # Sanitize authored provenance at the write boundary, not when reading saved snapshots.
        content = AssaySetupContent.model_validate(
            configuration_content(content.model_dump(exclude_computed_fields=True))
        )
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
        workspace = SetupWorkspace(
            content, self.store, document["created_by"], created_at=document["created_at"]
        )
        lists, _ = workspace.services(self.common_util)
        for config in content.gene_lists:
            values = workspace.document(config)
            values["asp_ids"] = [content.panel.asp_id]
            values["asp_groups"] = [content.panel.asp_group]
            lists.create(payload={"config": values}, actor_username=actor)
            if set(workspace.gene_lists[-1].get("diagnosis") or []) - set(content.scopes):
                raise api_error(422, "Gene-list diagnoses must be selected setup scopes")
        return workspace

    def reviewer_options(self, document: dict, *, actor: str) -> list[dict[str, str]]:
        """List active independent colleagues able to inspect and activate this setup.

        Args:
            document: Saved setup whose editors and shared-list links determine eligibility.
            actor: Submitting caller, excluded along with every content editor.

        Returns:
            Canonical usernames and display names, sorted for the reviewer selector.
        """
        required = {
            "assay.panel:list",
            "assay.panel:view",
            "assay.panel:edit",
            "assay.panel:create",
            "assay.config:create",
            "gene_list.insilico:create",
        }
        if document["content"].get("existing_gene_list_ids"):
            required.add("gene_list.insilico:edit")
        roles = {
            role["role_id"]: set(role.get("permissions") or [])
            for role in self.store.roles_repository.get_all_roles_plus_permissions()
            if role.get("is_active", True)
        }
        excluded = {str(value).strip().lower() for value in [actor, *document["content_editors"]]}
        choices = []
        for user in self.store.user_repository.list_active_users_for_notifications():
            username = str(user.get("username") or "").strip().lower()
            user_roles = set(user.get("roles") or []) & roles.keys()
            permissions = set().union(*(roles[role] for role in user_roles))
            if (
                username
                and username not in excluded
                and ("superuser" in user_roles or required <= permissions)
            ):
                choices.append({"username": username, "name": user.get("fullname") or username})
        return sorted(choices, key=lambda choice: (choice["name"].lower(), choice["username"]))

    def context(self, identifier: str | None, *, actor: str) -> dict:
        """Return managed forms, scope choices, rule references and saved progress.

        Args:
            identifier: Saved setup identifier, or None for the new assay form.
            actor: Caller used to build managed forms and validate staged resources.

        Returns:
            Form specifications and available scopes. Saved setups also include
            readiness, history and repairable validation errors. Environment choices
            include implicit production even for older persisted drafts.

        Raises:
            AppError: The requested saved setup does not exist.
        """
        result = {
            "panel_form": build_managed_form(managed_resource_spec("asp"), actor_username=actor),
            "diagnoses": self.store.assay_diagnosis_repository.list_definitions(),
            "environments": list(ENVIRONMENT_OPTIONS),
        }
        result["panel_form"]["fields"]["asp_group"]["options"] = (
            self.store.assay_panel_repository.group_options()
        )
        if not identifier:
            return result
        doc = self.get(identifier)
        result["setup"] = doc
        result["reviewers"] = self.reviewer_options(doc, actor=actor)
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
            content = AssaySetupContent.model_validate(doc["content"])
            workspace = SetupWorkspace(content, self.store, actor)
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
            result["configuration_form"]["fields"]["environment"]["options"] = content.environments
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
        """Require Base/production and validate all staged operational documents.

        Args:
            document: Saved setup snapshot containing assay, scopes and staged resources.
            actor: Username used to validate and attribute compiled resources.

        Returns:
            Validated activation bundle without writing operational resources.

        Raises:
            AppError: Configuration is incomplete, resolves an invalid rule,
                duplicates an identity or includes an unselected scope/environment.
        """
        content = AssaySetupContent.model_validate(document["content"])
        workspace = self._workspace(document, actor)
        _, configs = workspace.services(self.common_util)
        expected = {(scope, env) for scope in content.scopes for env in content.environments}
        actual = set()
        rules = {}
        warnings = []
        for source in content.configurations:
            config = workspace.document(source)
            config["asp_id"] = content.panel.asp_id
            key = (config.get("diagnosis_id") or "base", config.get("environment"))
            if key not in expected or key in actual:
                raise api_error(422, "ASPCs must use selected scopes/environments and be unique")
            configs.create(payload={"config": config}, actor_username=actor)
            actual.add(key)
            reporting = workspace.configurations[-1]["reporting"]
            try:
                rule = resolve_published_rule_set(
                    self.store.clinical_rule_set_repository,
                    asp_id=content.panel.asp_id,
                    diagnosis_id=key[0],
                    analyte=config["asp_category"].lower(),
                    language=reporting.get("language", "sv"),
                )
            except MissingClinicalRuleSet:
                warnings.append(f"{key[0]}/{key[1]}: {MISSING_REPORTING_RULES_WARNING}")
                continue
            except ValueError as exc:
                raise api_error(409, str(exc)) from exc
            rules[rule.rule_set_id] = rule.model_dump(mode="python", by_alias=True)
        if ("base", "production") not in actual:
            raise api_error(422, "Missing required ASPC: base/production")
        return {
            "panel": workspace.panel,
            "gene_lists": workspace.gene_lists,
            "linked_gene_lists": workspace.linked_lists,
            "configurations": workspace.configurations,
            "rules": list(rules.values()),
            "warnings": warnings,
            "definitions": workspace.definitions,
            "existing_lists": workspace.existing_lists,
            "associations": [
                {
                    "asp_id": content.panel.asp_id,
                    "diagnosis_id": d["diagnosis_id"],
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
            bundle = self.bundle(document, actor=actor)
            return {"ready": True, "issues": [], "warnings": bundle["warnings"]}
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
        identities.extend(
            (resource, configuration["aspc_id"], configuration[resource]["content_hash"], None)
            for configuration in bundle["configurations"]
            for resource in ("assay_resource_release", "gene_list_release")
        )
        identities.extend(
            (
                "configuration_profiles",
                configuration["aspc_id"],
                sha256(
                    json.dumps(
                        {
                            "sources": configuration.get("profile_sources", []),
                            "template": configuration.get("template_release"),
                        },
                        sort_keys=True,
                        default=str,
                    ).encode()
                ).hexdigest(),
                None,
            )
            for configuration in bundle["configurations"]
        )
        return sha256(json.dumps(sorted(identities), default=str).encode()).hexdigest()

    def transition(
        self,
        identifier: str,
        revision: int,
        action: str,
        *,
        actor: str,
        reason: str = "",
        assignee: str | None = None,
    ) -> dict:
        """Submit for optional review, return to draft, or publish a complete setup.

        Args:
            identifier: Saved setup identifier.
            revision: Revision loaded by the caller; stale requests are rejected.
            action: Submit a draft, return a submitted setup, or publish either state.
            actor: Authorized caller's username, retained in revision attribution.
            reason: Review or publication notes; required when returning to draft.
            assignee: Eligible colleague's username; required only for submission.

        Returns:
            Updated setup snapshot; publication atomically activates its resources.

        Raises:
            AppError: State, revision, validation or submitted dependencies prevent the action.
        """
        previous = self.get(identifier)
        allowed_states = {
            "submit": {"draft"},
            "return": {"submitted"},
            "publish": {"draft", "submitted"},
        }
        if (
            previous["status"] not in allowed_states.get(action, set())
            or previous["revision"] != revision
        ):
            raise api_error(409, "The setup state or revision does not allow this operation")
        if action == "return" and not reason.strip():
            raise api_error(422, "Explain which changes are required")
        reviewer = previous.get("reviewer")
        if action == "submit":
            reviewer = str(assignee or "").strip().lower()
            if not reviewer:
                raise api_error(422, "Select a reviewer before submitting")
            if reviewer not in {
                user["username"] for user in self.reviewer_options(previous, actor=actor)
            }:
                raise api_error(
                    422, "Select an active eligible reviewer who did not edit this setup"
                )
        bundle = self.bundle(previous, actor=actor) if action != "return" else None
        digest = self.dependency_hash(bundle) if bundle else None
        if (
            action == "publish"
            and previous["status"] == "submitted"
            and digest != previous.get("review_dependencies")
        ):
            raise api_error(
                409, "Setup dependencies changed after submission; return to draft and recheck them"
            )
        values = {
            **previous,
            "revision": revision + 1,
            "updated_by": actor,
            "updated_at": datetime.now(timezone.utc),
            "review_reason": reason,
            "status": {"submit": "submitted", "return": "draft", "publish": "published"}[action],
            "review_dependencies": digest,
            "reviewer": None if action == "return" else reviewer,
            "reviewed_by": actor if action == "publish" and actor == reviewer else None,
        }
        if action == "publish":
            values["published_by"] = actor
        return self.repository.save(
            values, previous=previous, action=action, bundle=bundle if action == "publish" else None
        )
