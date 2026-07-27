"""Casbin-backed RBAC/ABAC policy construction and enforcement."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import casbin

POLICY_MODEL = """
[request_definition]
r = sub, obj, act, assay, env, assay_group

[policy_definition]
p = sub, obj, act, eft

[role_definition]
g = _, _

[policy_effect]
e = some(where (p.eft == allow)) && !some(where (p.eft == deny))

[matchers]
m = (r.sub == p.sub || g(r.sub, p.sub)) && (p.obj == "*" || r.obj == p.obj) && r.act == p.act && has_scope(r.sub, r.assay, r.env, r.assay_group)
"""

POLICY_ACTION = "use"


def _norm(value: Any) -> str:
    return str(value or "").strip().lower()


def _norm_env(value: Any) -> str:
    """Normalize an already-canonical environment scope value."""
    return _norm(value)


def _unique(values: list[Any] | tuple[Any, ...] | set[Any] | None) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values or []:
        normalized = _norm(value)
        if normalized and normalized not in seen:
            result.append(normalized)
            seen.add(normalized)
    return result


def _principal_user(username: str) -> str:
    return f"user:{_norm(username)}"


def _principal_role(role_id: str) -> str:
    return f"role:{_norm(role_id)}"


@dataclass(frozen=True, slots=True)
class AccessContext:
    """Resource attributes used for scoped ABAC decisions."""

    assay: str = ""
    environment: str = ""
    assay_group: str = ""

    @classmethod
    def from_mapping(cls, context: dict[str, Any] | None = None) -> "AccessContext":
        """Build a normalized access context from route or resource metadata."""
        context = context or {}
        return cls(
            assay=_norm(context.get("assay")),
            environment=_norm_env(context.get("environment") or context.get("profile")),
            assay_group=_norm(context.get("assay_group")),
        )


@dataclass(frozen=True, slots=True)
class PrincipalScope:
    """ABAC scope attributes attached to an authenticated user."""

    assays: frozenset[str]
    environments: frozenset[str]
    assay_groups: frozenset[str]

    @classmethod
    def from_user(cls, user: Any) -> "PrincipalScope":
        """Build normalized scope attributes from the current user document."""
        return cls(
            assays=frozenset(_unique(getattr(user, "assays", []) or [])),
            environments=frozenset(
                _norm_env(value) for value in _unique(getattr(user, "envs", []) or [])
            ),
            assay_groups=frozenset(_unique(getattr(user, "assay_groups", []) or [])),
        )


def _scope_contains(scope_values: frozenset[str], required: str) -> bool:
    if not required:
        return True
    return "*" in scope_values or required in scope_values


def _active_permission_ids(permissions_repository: Any | None) -> set[str]:
    if permissions_repository is None:
        return set()
    try:
        docs = permissions_repository.get_all_permissions(is_active=True) or []
    except Exception:
        return set()
    active: set[str] = set()
    for doc in docs:
        if not isinstance(doc, dict):
            continue
        permission_id = _norm(doc.get("permission_id"))
        if permission_id:
            active.add(permission_id)
    return active


def _role_docs_by_id(roles_repository: Any | None) -> dict[str, dict[str, Any]]:
    if roles_repository is None:
        return {}
    try:
        docs = roles_repository.get_all_roles() or []
    except Exception:
        return {}
    roles: dict[str, dict[str, Any]] = {}
    for doc in docs:
        if not isinstance(doc, dict):
            continue
        role_id = _norm(doc.get("role_id"))
        if role_id and doc.get("is_active", True):
            roles[role_id] = dict(doc)
    return roles


@dataclass(slots=True)
class AccessPolicy:
    """Runtime authorization policy generated from users, roles and permissions."""

    enforcer: casbin.Enforcer
    active_permissions: set[str]
    principal_scope: PrincipalScope

    def permission_known(self, permission: str | None) -> bool:
        normalized = _norm(permission)
        return bool(normalized) and (
            not self.active_permissions or normalized in self.active_permissions
        )

    def permission_allowed(
        self,
        user: Any,
        permission: str | None,
        context: AccessContext | dict[str, Any] | None = None,
    ) -> bool:
        normalized = _norm(permission)
        if not normalized or not self.permission_known(normalized):
            return False
        access_context = (
            context if isinstance(context, AccessContext) else AccessContext.from_mapping(context)
        )
        return bool(
            self.enforcer.enforce(
                _principal_user(user.username),
                normalized,
                POLICY_ACTION,
                access_context.assay,
                access_context.environment,
                access_context.assay_group,
            )
        )

    def scope_allowed(self, user: Any, context: dict[str, Any] | None = None) -> bool:
        """Evaluate ABAC-style scope attributes when a route supplies them."""
        access_context = AccessContext.from_mapping(context)
        scope = self.principal_scope
        return (
            _scope_contains(scope.assays, access_context.assay)
            and _scope_contains(scope.environments, access_context.environment)
            and _scope_contains(scope.assay_groups, access_context.assay_group)
        )


def build_access_policy(
    *,
    user: Any,
    roles_repository: Any | None = None,
    permissions_repository: Any | None = None,
) -> AccessPolicy:
    """Build a Casbin policy from persisted role/user assignments."""
    model = casbin.Model()
    model.load_model_from_text(POLICY_MODEL)
    enforcer = casbin.Enforcer(model)

    active_permissions = _active_permission_ids(permissions_repository)
    role_docs = _role_docs_by_id(roles_repository)
    principal_scope = PrincipalScope.from_user(user)

    def _has_scope(_principal: str, assay: str, environment: str, assay_group: str) -> bool:
        return (
            _scope_contains(principal_scope.assays, _norm(assay))
            and _scope_contains(principal_scope.environments, _norm_env(environment))
            and _scope_contains(principal_scope.assay_groups, _norm(assay_group))
        )

    enforcer.add_function("has_scope", _has_scope)

    username = _principal_user(getattr(user, "username", ""))
    for role_id in _unique(getattr(user, "roles", []) or []):
        role_principal = _principal_role(role_id)
        enforcer.add_grouping_policy(username, role_principal)
        role_doc = role_docs.get(role_id, {})
        for permission in _unique(role_doc.get("permissions") if role_doc else []):
            if not active_permissions or permission in active_permissions:
                enforcer.add_policy(role_principal, permission, POLICY_ACTION, "allow")
    return AccessPolicy(
        enforcer=enforcer,
        active_permissions=active_permissions,
        principal_scope=principal_scope,
    )
