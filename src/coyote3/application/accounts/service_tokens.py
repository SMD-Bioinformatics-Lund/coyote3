"""Issue and revoke explicitly scoped automation identities without interactive logins."""

import hashlib
import secrets
from collections.abc import Callable, Sequence
from datetime import datetime, timedelta, timezone
from typing import Any, Literal, get_args
from uuid import uuid4

from coyote3.config.constants import ENVIRONMENT_OPTIONS
from coyote3.contracts.service_tokens import (
    SERVICE_TOKEN_PREFIX,
    PersonalTokenCreate,
    ServiceTokenCreate,
    ServiceTokenIssued,
    ServiceTokenMetadata,
    ServiceTokenOperation,
    ServiceTokenOptions,
    TokenScopeCreate,
)
from coyote3.domain.common.errors import api_error
from coyote3.domain.service_tokens import ServiceTokenRepository


class ServiceTokens:
    """Manage secret-free metadata and verify live credential state before each operation."""

    def __init__(
        self,
        repository: ServiceTokenRepository,
        *,
        users: Any,
        assays: Any,
        audience: str,
        audit: Any = None,
        user_loader: Callable[[str], Any] | None = None,
        permission_check: Callable[[Any, str | None, dict[str, Any] | None], bool] | None = None,
    ) -> None:
        """Bind identity storage, active registries, deployment audience and durable audit.

        Args:
            repository: Identity-database credential persistence; never receives raw secrets.
            users: Current owner activation lookup and active owner choices.
            assays: Active registered assay choices; identifiers are never guessed.
            audience: Destination deployment environment, distinct from clinical environments.
            audit: Durable event writer; None means credential issuance is unavailable.
            user_loader: Current active identity resolver for personal-token delegation.
            permission_check: Current permission/scope evaluator; None disables personal issuance.
        """
        self.repository = repository
        self.users, self.assays, self.audience, self.audit = users, assays, audience, audit
        self.user_loader, self.permission_check = user_loader, permission_check

    def options(self, *, include_owners: bool = True) -> ServiceTokenOptions:
        """Return selectable registered scopes and ingestion operations.

        Args:
            include_owners: Include active owner choices for administrators. Personal-token
                workflows pass False and never enumerate other accounts.

        Returns:
            Active assay choices, configured environments, supported operations and optional owners.
        """
        return ServiceTokenOptions(
            owners=[
                {"username": user["username"], "name": user.get("fullname") or user["username"]}
                for user in (
                    self.users.list_active_users_for_notifications() if include_owners else []
                )
            ],
            assays=[
                {"asp_id": panel["asp_id"], "name": panel.get("display_name") or panel["asp_id"]}
                for panel in self.assays.get_all_asps(is_active=True)
            ],
            environments=list(ENVIRONMENT_OPTIONS),
            operations=list(get_args(ServiceTokenOperation)),
        )

    def issue(self, payload: ServiceTokenCreate, *, actor: Any) -> ServiceTokenIssued:
        """Issue a secret once after validating its owner and each explicit scope.

        Args:
            payload: Selected operations, registered assays, environments and bounded lifetime.
            actor: Authorized administrator recorded as issuer; never used as the service identity.

        Returns:
            Raw secret and public metadata. Persistence receives only the secret's SHA-256 digest.

        Raises:
            AppError: The owner is inactive or a scope is unregistered.
        """
        return self._issue(payload, owner=payload.owner, kind="service", actor=actor)

    def issue_personal(self, payload: PersonalTokenCreate, *, actor: Any) -> ServiceTokenIssued:
        """Issue an ingestion-only personal credential bounded by the user's current access.

        Args:
            payload: Explicit operations, assays, environments and expiry; contains no owner field.
            actor: Current authenticated user, always the new credential's owner.

        Returns:
            One-time secret and personal credential metadata.

        Raises:
            AppError: Selected permissions/scopes exceed current access or audit is unavailable.
        """
        return self._issue(payload, owner=actor.username, kind="personal", actor=actor)

    def personal_options(self, *, actor: Any) -> ServiceTokenOptions:
        """List only registered assays and environments within the current user's scope."""
        options = self.options(include_owners=False)
        pairs = [
            (assay["asp_id"], env)
            for assay in options.assays
            for env in options.environments
            if self.personal_allowed(actor, None, {"asp_id": assay["asp_id"], "environment": env})
        ]
        return ServiceTokenOptions(
            owners=[],
            assays=[
                assay
                for assay in options.assays
                if any(pair[0] == assay["asp_id"] for pair in pairs)
            ],
            environments=[
                env for env in options.environments if any(pair[1] == env for pair in pairs)
            ],
            operations=[
                operation
                for operation in options.operations
                if any(
                    all(
                        self.personal_allowed(
                            actor, permission, {"asp_id": asp_id, "environment": environment}
                        )
                        for permission in self._required_permissions([operation])
                    )
                    for asp_id, environment in pairs
                )
            ],
        )

    def _issue(
        self,
        payload: TokenScopeCreate,
        *,
        owner: str,
        kind: Literal["service", "personal"],
        actor: Any,
    ) -> ServiceTokenIssued:
        """Validate scopes and persist a credential only with durable lifecycle auditing."""
        if not self._active_owner(owner):
            raise api_error(422, "Choose an active owner for this service token")
        options = self.options(include_owners=False)
        if not set(payload.asp_ids) <= {item["asp_id"].lower() for item in options.assays}:
            raise api_error(422, "Choose registered active assays")
        if not set(payload.environments) <= set(options.environments):
            raise api_error(422, "Choose configured clinical environments")
        if kind == "personal":
            for asp_id in payload.asp_ids:
                for environment in payload.environments:
                    for permission in self._required_permissions(payload.operations):
                        if not self.personal_allowed(
                            actor, permission, {"asp_id": asp_id, "environment": environment}
                        ):
                            raise api_error(
                                403, "Personal token selections exceed your current access"
                            )
        if self.audit is None:
            raise api_error(503, "Service-token audit storage is unavailable")
        now = datetime.now(timezone.utc)
        metadata = ServiceTokenMetadata(
            token_id=uuid4().hex,
            kind=kind,
            name=payload.name,
            owner=owner,
            operations=sorted(set(payload.operations)),
            asp_ids=payload.asp_ids,
            environments=payload.environments,
            audience=self.audience,
            created_by=actor.username,
            created_at=now,
            expires_at=now + timedelta(hours=payload.expires_hours),
        )
        token = SERVICE_TOKEN_PREFIX + secrets.token_urlsafe(48)
        self.repository.create({**metadata.model_dump(), "token_hash": self._digest(token)})
        try:
            self._record("issued", metadata, actor)
        except Exception:
            self.repository.revoke(metadata.token_id, actor=actor.username, now=now)
            raise
        return ServiceTokenIssued(token=token, metadata=metadata)

    def list_metadata(
        self, *, owner: str | None = None, kind: str | None = None
    ) -> list[ServiceTokenMetadata]:
        """Return the latest 500 matching credentials without secrets or hashes.

        Args:
            owner: Exact account filter for personal lists; None allows all owners for admins.
            kind: Restrict to service or personal metadata; None permits either kind.

        Returns:
            Matching metadata in creation order, newest first, including revoked/expired records.
        """
        return [
            ServiceTokenMetadata.model_validate(row)
            for row in self.repository.list_metadata(owner=owner, kind=kind)
        ]

    def revoke(
        self, token_id: str, *, actor: Any, personal_only: bool = False
    ) -> ServiceTokenMetadata:
        """Revoke future operations immediately without deleting credential history.

        Args:
            token_id: Public credential identifier; never the credential secret.
            actor: Authorized administrator recorded for revocation attribution.
            personal_only: Require the actor to own a personal credential; admin callers use False.

        Returns:
            Public metadata preserving the original revocation on retries.

        Raises:
            AppError: No credential has the supplied public identifier.
        """
        if personal_only:
            row = self.repository.get_metadata(token_id)
            if row is None or row["owner"] != actor.username or row["kind"] != "personal":
                raise api_error(404, "Personal token was not found")
        row = self.repository.revoke(token_id, actor=actor.username, now=datetime.now(timezone.utc))
        if row is None:
            raise api_error(404, "Service token was not found")
        metadata = ServiceTokenMetadata.model_validate(row)
        self._record("revoked", metadata, actor)
        return metadata

    def resolve(self, token: str) -> ServiceTokenMetadata | None:
        """Resolve a raw credential against current expiry, revocation, audience and owner.

        Args:
            token: Complete opaque bearer secret including the service-token family prefix.

        Returns:
            Public scope metadata, or None for an invalid credential or disabled owner.
        """
        if not token.startswith(SERVICE_TOKEN_PREFIX) or len(token) > 200:
            return None
        row = self.repository.resolve(
            self._digest(token), audience=self.audience, now=datetime.now(timezone.utc)
        )
        if row is None or not self._active_owner(row["owner"]):
            return None
        return ServiceTokenMetadata.model_validate(row)

    def _active_owner(self, owner: str) -> bool:
        """Require an existing active accountable owner on issuance and credential use."""
        user = self.users.user_with_id(owner)
        return bool(user and user.get("is_active", True))

    def personal_actor(self, metadata: ServiceTokenMetadata) -> Any:
        """Reload the active personal-token owner; fail closed if delegation is unavailable."""
        actor = self.user_loader(metadata.owner) if self.user_loader is not None else None
        if actor is None or getattr(actor, "must_change_password", False):
            raise api_error(401, "Personal token owner is unavailable")
        return actor

    def authorize_job(self, job: dict[str, Any]) -> None:
        """Recheck a queued token's live authority before the worker performs any writes.

        Args:
            job: Repository-loaded durable job; contains only a public credential reference.

        Raises:
            AppError: The credential expired, was revoked, lost permission or no longer covers
                the stored operation and manifest scope. Standard session jobs keep their behavior.
        """
        token_id = job.get("credential_id")
        if not token_id:
            if any(
                job.get(key)
                for key in ("credential_owner", "credential_operation", "credential_scope")
            ):
                raise api_error(403, "Queued token job has an incomplete credential reference")
            return
        row = self.repository.resolve_id(
            token_id, audience=self.audience, now=datetime.now(timezone.utc)
        )
        if row is None or not self._active_owner(row["owner"]):
            raise api_error(403, "Queued ingestion credential is expired, revoked or disabled")
        metadata = ServiceTokenMetadata.model_validate(row)
        operation = job.get("credential_operation")
        if job.get("credential_owner") != metadata.owner:
            raise api_error(403, "Queued ingestion owner does not match its token")
        if (
            job["kind"] != "sample_bundle"
            or operation not in {"sample_bundle_async", "sample_upload_async"}
            or operation not in metadata.operations
        ):
            raise api_error(403, "Queued ingestion operation is outside token access")
        expected = (
            metadata.owner if metadata.kind == "personal" else "service-token-" + metadata.token_id
        )
        if job["submitted_by"] != expected:
            raise api_error(403, "Queued ingestion identity does not match its token")
        payload = job.get("source_payload") or {}
        context = {
            "asp_id": str(payload.get("asp_id") or "").lower(),
            "environment": str(payload.get("environment") or "").lower(),
        }
        if job.get("credential_scope") != context:
            raise api_error(403, "Queued ingestion scope does not match its credential reference")
        if (
            context["asp_id"] not in metadata.asp_ids
            or context["environment"] not in metadata.environments
        ):
            raise api_error(403, "Queued ingestion scope is outside token access")
        if metadata.kind == "personal":
            actor = self.personal_actor(metadata)
            for permission in ("internal.ingest:manage", "sample:edit:own"):
                if not self.personal_allowed(actor, permission, context):
                    raise api_error(403, "Personal token owner no longer has ingestion access")

    def personal_allowed(
        self, actor: Any, permission: str | None, context: dict[str, Any] | None
    ) -> bool:
        """Evaluate live account grants without treating a token as an independent user role."""
        return bool(
            self.permission_check is not None and self.permission_check(actor, permission, context)
        )

    @staticmethod
    def _required_permissions(operations: Sequence[str]) -> set[str]:
        """Map selected ingestion capabilities to the existing application permission catalog."""
        permissions = set()
        if "job_status" in operations:
            permissions.add("internal.task:view")
        if any(operation != "job_status" for operation in operations):
            permissions.update({"internal.ingest:manage", "sample:edit:own"})
        return permissions

    @staticmethod
    def _digest(token: str) -> str:
        """Hash a high-entropy credential for lookup without persisting its secret."""
        return hashlib.sha256(token.encode()).hexdigest()

    def _record(self, action: str, metadata: ServiceTokenMetadata, actor: Any) -> None:
        """Record credential lifecycle metadata without either secret or digest."""
        if self.audit is None or not self.audit.record(
            f"service_token.{action}",
            f"Service token {action}",
            actor=actor,
            category="security",
            resource_type="service_token",
            resource_id=metadata.token_id,
            metadata=metadata.model_dump(mode="json"),
        ):
            raise api_error(503, "Service-token audit storage is unavailable")
