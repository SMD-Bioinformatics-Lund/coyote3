"""Unit tests for admin workflow services."""

from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

import coyote3.application.accounts.permissions as admin_permission_service_module
import coyote3.application.accounts.roles as admin_role_service_module
import coyote3.application.accounts.users as admin_user_service_module
import coyote3.application.resources.asp as admin_asp_service_module
import coyote3.application.resources.aspc as admin_aspc_service_module
import coyote3.application.resources.isgl as admin_isgl_service_module
import coyote3.application.resources.sample as admin_resource_service_module
from api.app.container import util as shared_util
from api.infra.mongo.repositories.assay_configurations import ASPConfigRepository
from coyote3.application.accounts.permissions import PermissionManagementService
from coyote3.application.accounts.roles import RoleManagementService
from coyote3.application.accounts.users import UserManagementService
from coyote3.application.resources.asp import AspService
from coyote3.application.resources.aspc import AspcService
from coyote3.application.resources.isgl import IsglService
from coyote3.application.resources.sample import ResourceSampleService
from coyote3.config.constants import (
    ASP_CATEGORY_OPTIONS,
    ASP_FAMILY_OPTIONS,
    PLATFORM_OPTIONS,
    SAMPLE_FILE_KEYS,
)
from coyote3.config.contracts.governance import PERMISSION_CATALOG
from coyote3.contracts.operations import OperationResult
from coyote3.domain.exceptions import AppError


class _AdminRepoStub:
    """Provide  AdminRepoStub behavior."""

    def __init__(self) -> None:
        """__init__."""
        self.created_user = None
        self.updated_user = None
        self.created_role = None
        self.updated_role = None
        self.deleted_users: list[str] = []
        self.deleted_roles: list[str] = []

    def list_users(self):
        """List users."""
        return [{"_id": "tester", "user_id": "tester"}]

    def search_users(self, *, q="", page=1, per_page=30):
        """Search users."""
        _ = (q, page, per_page)
        return ([{"_id": "tester", "user_id": "tester"}], 1)

    def get_role_colors(self):
        """Return role colors."""
        return {"admin": "#000"}

    def list_permission_policy_options(self):
        """List permission policy options."""
        return [{"value": "perm.a", "label": "perm.a", "category": "General"}]

    def get_role_names(self):
        """Return role names."""
        return ["admin"]

    def get_roles_policy_map(self):
        """Return roles policy map."""
        return {"admin": {"permissions": ["perm.a"], "level": 99}}

    def get_assay_group_map(self):
        """Return assay group map."""
        return {"dna": [{"_id": "WGS"}]}

    def get_asp_groups(self):
        """Return asp groups."""
        return ["dna"]

    def create_user(self, user_data):
        """Create user."""
        self.created_user = user_data

    def get_user(self, user_id):
        """Return user."""
        if user_id in {"missing", "newtester"}:
            return None
        return {
            "_id": "tester",
            "username": "tester",
            "email": "tester@example.com",
            "firstname": "Test",
            "lastname": "User",
            "fullname": "Test User",
            "job_title": "Analyst",
            "roles": ["admin"],
            "password": "hashed",
            "version": 3,
            "asp_groups": [],
            "asp_ids": [],
            "environments": ["production"],
            "is_active": True,
            "auth_type": ["ldap"],
        }

    def update_user(self, user_id, user_data, *, fields, expected_version):
        """Update user."""
        self.updated_user = (user_id, user_data)
        return SimpleNamespace(matched_count=1)

    def delete_user(self, user_id, *, expected_version):
        """Delete user."""
        self.deleted_users.append(user_id)
        return SimpleNamespace(deleted_count=1)

    def set_user_active(self, user_id, is_active):
        """Set user active."""
        self.updated_user = (user_id, {"is_active": is_active})

    @property
    def user_repository(self):
        """User handler."""
        return type(
            "_UserHandler",
            (),
            {
                "user_exists": staticmethod(
                    lambda **kwargs: (
                        kwargs.get("user_id") == "taken"
                        or kwargs.get("email") == "taken@example.com"
                    )
                )
            },
        )()

    def list_roles(self):
        """List roles."""
        return [{"_id": "admin", "role_id": "admin", "level": 99}]

    def search_roles(self, *, q="", page=1, per_page=30):
        """Search roles."""
        _ = (q, page, per_page)
        return ([{"_id": "admin", "role_id": "admin", "level": 99}], 1)

    def get_role(self, role_id):
        """Return role."""
        if role_id in {"missing", "developer"}:
            return None
        return {
            "_id": "admin",
            "role_id": "admin",
            "name": "Admin",
            "permissions": [],
            "version": 4,
        }

    def create_role(self, role_data):
        """Create role."""
        self.created_role = role_data

    def update_role(self, role_id, role_data):
        """Update role."""
        self.updated_role = (role_id, role_data)

    def set_role_active(self, role_id, is_active):
        """Set role active."""
        self.updated_role = (role_id, {"is_active": is_active})

    def delete_role(self, role_id):
        """Delete role."""
        self.deleted_roles.append(role_id)

    def list_permissions(self, *, is_active=False):
        """List permissions."""
        return [
            {
                "_id": "sample:view",
                "permission_id": "sample:view",
                "category": "General",
                "is_active": True,
            }
        ]

    def search_permissions(self, *, q="", page=1, per_page=30, is_active=False):
        """Search permissions."""
        _ = (q, page, per_page, is_active)
        return (
            [
                {
                    "_id": "sample:view",
                    "permission_id": "sample:view",
                    "category": "General",
                    "is_active": True,
                }
            ],
            1,
        )

    def get_permission(self, permission_id):
        """Return permission."""
        if permission_id in {"missing", "sample:create"}:
            return None
        return {
            "_id": permission_id,
            "permission_id": permission_id,
            "version": 4,
            "is_active": True,
            "category": "General",
        }

    def create_permission(self, policy):
        """Create permission."""
        self.created_permission = policy

    def update_permission(self, permission_id, policy):
        """Update permission."""
        self.updated_permission = (permission_id, policy)

    def set_permission_active(self, permission_id, is_active):
        """Set permission active."""
        self.updated_permission = (permission_id, {"is_active": is_active})

    def delete_permission(self, permission_id):
        """Delete permission."""
        self.deleted_permissions = getattr(self, "deleted_permissions", [])
        self.deleted_permissions.append(permission_id)

    def list_panels(self, *, is_active=None):
        """List panels."""

    def get_panel(self, panel_id):
        """Return panel."""
        if panel_id == "missing":
            return None
        return {
            "_id": panel_id,
            "asp_id": panel_id,
            "asp_group": "dna",
            "is_active": False,
            "covered_genes": ["TP53"],
            "expected_files": ["vcf_files"],
            "germline_genes": ["BRCA1"],
        }

    def create_panel(self, panel):
        """Create panel."""
        self.created_panel = panel

    def update_panel(self, panel_id, panel):
        """Update panel."""
        self.updated_panel = (panel_id, panel)

    def rotate_panel(self, panel_id, panel, expected_version=None, retire_fields=None):
        """Rotate panel."""
        self.updated_panel = (panel_id, panel, expected_version, retire_fields or {})
        return OperationResult(inserted_count=1, inserted_id="new-panel-id")

    def set_panel_active(self, panel_id, is_active):
        """Set panel active."""
        self.updated_panel = (panel_id, {"is_active": is_active})

    def delete_panel(self, panel_id):
        """Delete panel."""
        self.deleted_panels = getattr(self, "deleted_panels", [])
        self.deleted_panels.append(panel_id)

    def list_genelists(self):
        """List genelists."""
        return [
            {
                "_id": "GL1",
                "isgl_id": "GL1",
                "genes": ["TP53"],
                "asp_ids": ["WGS"],
            }
        ]

    def get_genelist(self, genelist_id):
        """Return genelist."""
        if genelist_id == "missing":
            return None
        return {
            "_id": genelist_id,
            "isgl_id": genelist_id,
            "genes": ["TP53", "EGFR"],
            "asp_ids": ["WGS"],
            "asp_groups": ["dna"],
            "is_active": True,
        }

    def create_genelist(self, genelist):
        """Create genelist."""
        self.created_genelist = genelist

    def update_genelist(self, genelist_id, genelist):
        """Update genelist."""
        self.updated_genelist = (genelist_id, genelist)

    def rotate_genelist(self, genelist_id, genelist, expected_version=None, retire_fields=None):
        """Rotate genelist."""
        self.updated_genelist = (genelist_id, genelist, expected_version, retire_fields or {})
        return OperationResult(inserted_count=1, inserted_id="new-genelist-id")

    def set_genelist_active(self, genelist_id, is_active):
        """Set genelist active."""
        self.updated_genelist = (genelist_id, {"is_active": is_active})

    def delete_genelist(self, genelist_id):
        """Delete genelist."""
        self.deleted_genelists = getattr(self, "deleted_genelists", [])
        self.deleted_genelists.append(genelist_id)

    def list_assay_configs(self):
        """List assay configs."""
        return [{"_id": "WGS:prod", "aspc_id": "WGS:prod", "is_active": True}]

    def get_assay_config(self, assay_id):
        """Return assay config."""
        if assay_id == "missing":
            return None
        return {"_id": assay_id, "aspc_id": assay_id, "is_active": True}

    def create_assay_config(self, config):
        """Create assay config."""
        self.created_aspc = config

    def update_assay_config(self, assay_id, config):
        """Update assay config."""
        self.updated_aspc = (assay_id, config)

    def rotate_assay_config(self, assay_id, config, expected_version=None, retire_fields=None):
        """Rotate assay config."""
        self.updated_aspc = (assay_id, config, expected_version, retire_fields or {})
        return OperationResult(inserted_count=1, inserted_id="new-aspc-id")

    def set_assay_config_active(self, assay_id, is_active):
        """Set assay config active."""
        self.updated_aspc = (assay_id, {"is_active": is_active})

    def delete_assay_config(self, assay_id):
        """Delete assay config."""
        self.deleted_aspc = getattr(self, "deleted_aspc", [])
        self.deleted_aspc.append(assay_id)

    def get_available_assay_envs(self, assay_id, allowed_envs):
        """Return available assay envs."""
        return ["production"]

    def list_samples_for_admin(
        self,
        *,
        asp_ids=None,
        search_str="",
        page=1,
        per_page=30,
        ready_only=True,
    ):
        """List samples for admin."""
        _ = (asp_ids, search_str, page, per_page, ready_only)
        return ([{"_id": "S1"}], 1)

    def search_panels(self, *, q="", page=1, per_page=30, is_active=None):
        """Search panels."""
        _ = (q, page, per_page, is_active)
        return ([{"_id": "asp1"}], 1)

    def search_genelists(self, *, q="", page=1, per_page=30):
        """Search genelists."""
        _ = (q, page, per_page)
        return ([{"_id": "isgl1"}], 1)

    def search_assay_configs(self, *, q="", page=1, per_page=30):
        """Search assay configs."""
        _ = (q, page, per_page)
        return ([{"_id": "aspc1"}], 1)

    def search_schemas(self, *, q="", page=1, per_page=30):
        """Search schemas."""
        _ = (q, page, per_page)
        return ([{"_id": "schema1"}], 1)

    def get_sample(self, sample_id):
        """Return sample."""
        if sample_id == "missing":
            return None
        return {
            "_id": sample_id,
            "sample_id": sample_id,
            "asp_id": "hema_gmsv1",
            "diagnosis_id": "base",
            "environment": "production",
            "asp_category": "dna",
            "version": 1,
            "asp_family": "panel-dna",
        }

    def update_sample(self, sample_obj, updated_sample):
        """Update sample."""
        self.updated_sample_doc = (sample_obj, updated_sample)

    def get_sample_name(self, sample_id):
        """Return sample name."""
        if sample_id == "missing":
            return None
        return sample_id

    def list_schemas(self):
        """List schemas."""
        return [{"_id": "schema1"}]

    def create_schema(self, schema_doc):
        """Create schema."""
        self.created_schema = schema_doc

    def update_schema(self, schema_id, schema_doc):
        """Update schema."""
        self.updated_schema = (schema_id, schema_doc)

    def set_schema_active(self, schema_id, is_active):
        """Set schema active."""
        self.updated_schema = (schema_id, {"is_active": is_active})

    def delete_schema(self, schema_id):
        """Delete schema."""
        self.deleted_schemas = getattr(self, "deleted_schemas", [])
        self.deleted_schemas.append(schema_id)


def _build_store(repo: _AdminRepoStub) -> SimpleNamespace:
    def active_rule_set(rule_set_id: str):
        return {
            "rule_set_id": rule_set_id,
            "content_version": 1,
            "revision": 1,
            "scope": {
                "asp_id": rule_set_id.split("__", 1)[0],
                "diagnosis_id": "base",
                "analyte": "dna",
                "language": "sv",
            },
            "name": "Test rules",
            "status": "published",
            "active": True,
            "analysis_declarations": {
                analysis: {"narrative": "enabled"}
                for analysis in (
                    "SNV",
                    "CNV",
                    "TRANSLOCATION",
                    "HRD",
                    "MSI",
                    "COVERAGE",
                    "TMB",
                    "PGX",
                    "CNV_PROFILE",
                )
            },
            "blocks": [],
            "created_at": "2026-01-01T00:00:00Z",
            "created_by": "test",
            "updated_at": "2026-01-01T00:00:00Z",
            "updated_by": "test",
            "published_at": "2026-01-01T00:00:00Z",
            "published_by": "test",
        }

    return SimpleNamespace(
        user_repository=SimpleNamespace(
            search_users=repo.search_users,
            user_with_id=repo.get_user,
            create_user=repo.create_user,
            update_user=repo.update_user,
            toggle_user_active=repo.set_user_active,
            delete_user=repo.delete_user,
            user_exists=repo.user_repository.user_exists,
        ),
        roles_repository=SimpleNamespace(
            search_roles=repo.search_roles,
            get_role_colors=repo.get_role_colors,
            get_all_role_names=repo.get_role_names,
            get_all_roles=lambda: [
                {
                    "role_id": role_id,
                    "permissions": role_data.get("permissions", []),
                    "level": role_data.get("level", 0),
                }
                for role_id, role_data in repo.get_roles_policy_map().items()
            ],
            get_role=repo.get_role,
            create_role=repo.create_role,
            update_role=repo.update_role,
            toggle_role_active=repo.set_role_active,
            delete_role=repo.delete_role,
        ),
        permissions_repository=SimpleNamespace(
            search_permissions=repo.search_permissions,
            get_all_permissions=repo.list_permissions,
            get_permission=repo.get_permission,
            create_new_policy=repo.create_permission,
            update_policy=repo.update_permission,
            toggle_policy_active=repo.set_permission_active,
            delete_policy=repo.delete_permission,
        ),
        vep_metadata_repository=SimpleNamespace(
            get_consequence_group_options=lambda vep=None: ["missense", "splicing"],
        ),
        assay_panel_repository=SimpleNamespace(
            group_options=lambda: ["hematology", "solid", "custom-group", "dna"],
            search_asps=repo.search_panels,
            get_all_asp_groups=repo.get_asp_groups,
            get_all_asps=lambda is_active=None: [repo.get_panel("WGS")],
            get_asp=repo.get_panel,
            create_panel=repo.create_panel,
            update_asp=repo.update_panel,
            rotate_asp=repo.rotate_panel,
            toggle_asp_active=repo.set_panel_active,
            delete_panel=repo.delete_panel,
        ),
        gene_list_repository=SimpleNamespace(
            search_isgls=repo.search_genelists,
            get_all_isgl=repo.list_genelists,
            get_isgl=repo.get_genelist,
            get_isgl_for_scope=lambda asp_name=None, assay_group=None, is_active=None, adhoc=None: [
                item
                for item in repo.list_genelists()
                if (
                    asp_name in (item.get("asp_ids") or [])
                    or assay_group in (item.get("asp_groups") or [])
                )
                and (is_active is None or item.get("is_active") is is_active)
                and (adhoc is None or item.get("adhoc") is adhoc)
            ],
            create_genelist=repo.create_genelist,
            update_isgl=repo.update_genelist,
            rotate_isgl=repo.rotate_genelist,
            toggle_isgl_active=repo.set_genelist_active,
            delete_genelist=repo.delete_genelist,
        ),
        assay_configuration_repository=SimpleNamespace(
            build_aspc_id=ASPConfigRepository.build_aspc_id,
            search_aspcs=repo.search_assay_configs,
            get_aspc=repo.get_assay_config,
            get_aspc_with_id=repo.get_assay_config,
            get_available_assay_envs=repo.get_available_assay_envs,
            create_assay_config=repo.create_assay_config,
            update_aspc=repo.update_assay_config,
            rotate_aspc=repo.rotate_assay_config,
            toggle_aspc_active=repo.set_assay_config_active,
            delete_assay_config=repo.delete_assay_config,
        ),
        sample_repository=SimpleNamespace(
            search_samples_for_admin=repo.list_samples_for_admin,
            get_sample=repo.get_sample,
            update_sample=repo.update_sample,
            get_sample_name=repo.get_sample_name,
        ),
        variant_repository=SimpleNamespace(),
        copy_number_variant_repository=SimpleNamespace(),
        d4_coverage_repository=SimpleNamespace(),
        translocation_repository=SimpleNamespace(),
        fusion_repository=SimpleNamespace(),
        biomarker_repository=SimpleNamespace(),
        rna_expression_repository=SimpleNamespace(),
        rna_classification_repository=SimpleNamespace(),
        rna_quality_repository=SimpleNamespace(),
        pgx_repository=SimpleNamespace(),
        sample_comment_repository=SimpleNamespace(),
        finding_comment_repository=SimpleNamespace(),
        report_repository=SimpleNamespace(),
        reported_variant_repository=SimpleNamespace(),
        oncokb_public_cache_repository=SimpleNamespace(),
        clinical_rule_set_repository=SimpleNamespace(
            get_active=active_rule_set,
            list_active_for_assay=lambda asp_id, **_scope: [],
        ),
    )


def _user_service(repo: _AdminRepoStub) -> UserManagementService:
    store = _build_store(repo)
    return UserManagementService(
        password_token_issuer=lambda **_: {},
        user_change_notifier=lambda **_: {},
        user_repository=store.user_repository,
        roles_repository=store.roles_repository,
        permissions_repository=store.permissions_repository,
        assay_panel_repository=store.assay_panel_repository,
        common_util=shared_util.common,
    )


def _role_service(repo: _AdminRepoStub) -> RoleManagementService:
    store = _build_store(repo)
    return RoleManagementService(
        roles_repository=store.roles_repository,
        permissions_repository=store.permissions_repository,
    )


def _permission_service(repo: _AdminRepoStub) -> PermissionManagementService:
    store = _build_store(repo)
    return PermissionManagementService(permissions_repository=store.permissions_repository)


def _asp_service(repo: _AdminRepoStub) -> AspService:
    store = _build_store(repo)
    return AspService(assay_panel_repository=store.assay_panel_repository)


def _isgl_service(repo: _AdminRepoStub) -> IsglService:
    store = _build_store(repo)
    return IsglService(
        assay_diagnosis_repository=SimpleNamespace(list_for_assay=lambda *_a, **_k: []),
        gene_list_repository=store.gene_list_repository,
        assay_panel_repository=store.assay_panel_repository,
    )


def _aspc_service(repo: _AdminRepoStub) -> AspcService:
    store = _build_store(repo)
    return AspcService(
        assay_diagnosis_repository=SimpleNamespace(
            list_for_assay=lambda *_a, **_k: [
                {"diagnosis_id": "base", "display_name": "Base"},
                {"diagnosis_id": "aml", "display_name": "AML"},
            ]
        ),
        assay_configuration_repository=store.assay_configuration_repository,
        assay_panel_repository=store.assay_panel_repository,
        gene_list_repository=store.gene_list_repository,
        vep_metadata_repository=store.vep_metadata_repository,
    )


def _resource_sample_service(repo: _AdminRepoStub) -> ResourceSampleService:
    store = _build_store(repo)
    return ResourceSampleService(
        sample_repository=store.sample_repository,
        assay_panel_repository=store.assay_panel_repository,
        sample_deleter=Mock(),
    )


def _patch_admin_stores(monkeypatch, repo: _AdminRepoStub) -> None:
    store = _build_store(repo)
    for module in (
        admin_user_service_module,
        admin_role_service_module,
        admin_permission_service_module,
        admin_asp_service_module,
        admin_aspc_service_module,
        admin_isgl_service_module,
        admin_resource_service_module,
    ):
        monkeypatch.setattr(module, "store", store, raising=False)


def test_admin_user_service_create_user_normalizes_identity(monkeypatch):
    repo = _AdminRepoStub()
    _patch_admin_stores(monkeypatch, repo)
    service = _user_service(repo)
    monkeypatch.setattr(
        "coyote3.application.accounts.users.current_actor", lambda username: username
    )
    monkeypatch.setattr(
        "coyote3.application.accounts.users.utc_now", lambda: datetime.now(timezone.utc)
    )
    monkeypatch.setattr(
        shared_util,
        "records",
        SimpleNamespace(
            normalize_form_payload=lambda form_data, schema: {
                "username": form_data["username"],
                "email": form_data["email"],
                "firstname": form_data.get("firstname", "Test"),
                "lastname": form_data.get("lastname", "User"),
                "fullname": form_data.get("fullname", "Test User"),
                "job_title": form_data.get("job_title", "Analyst"),
                "roles": form_data["roles"],
                "auth_type": ["ldap"],
                "password": "secret",
            }
        ),
        raising=False,
    )
    monkeypatch.setattr(
        shared_util,
        "common",
        SimpleNamespace(hash_password=lambda raw: f"H:{raw}"),
        raising=False,
    )
    service = UserManagementService(
        password_token_issuer=lambda **_: {},
        user_change_notifier=lambda **_: {},
        user_repository=service.user_repository,
        roles_repository=service.roles_repository,
        permissions_repository=service.permissions_repository,
        assay_panel_repository=service.assay_panel_repository,
        common_util=shared_util.common,
    )

    payload = service.create_user(
        payload={
            "form_data": {
                "username": "NewTester",
                "email": "NewTester@Example.com",
                "password": "secret",
                "roles": ["admin"],
            }
        },
        actor_username="actor@example.com",
    )

    assert payload["resource"] == "user"
    assert repo.created_user["username"] == "newtester"
    assert repo.created_user["email"] == "newtester@example.com"
    assert repo.created_user["auth_type"] == ["ldap"]
    assert repo.created_user["password"] is None
    assert "permissions" not in repo.created_user


def test_admin_user_service_toggle_user_sets_status(monkeypatch):
    repo = _AdminRepoStub()
    _patch_admin_stores(monkeypatch, repo)
    service = _user_service(repo)

    payload = service.toggle_user(user_id="tester")

    assert payload["meta"]["is_active"] is False
    assert repo.updated_user == ("tester", {"is_active": False})


def test_admin_user_edit_rejects_password_fields():
    """Generic user administration must not mutate credentials."""
    service = _user_service(_AdminRepoStub())

    with pytest.raises(AppError, match="Passwords cannot be changed") as exc_info:
        service.update_user(
            user_id="tester",
            payload={"form_data": {"password": "replacement"}},
            actor_username="manager",
        )

    assert exc_info.value.status_code == 400


def test_non_superuser_cannot_assign_superuser_role():
    """The user-edit capability does not grant the superuser boundary."""
    service = _user_service(_AdminRepoStub())

    with pytest.raises(AppError, match="Only a superuser") as exc_info:
        service.create_user(
            payload={
                "form_data": {
                    "username": "elevated.user",
                    "email": "elevated@example.com",
                    "roles": ["superuser"],
                }
            },
            actor_username="manager",
        )

    assert exc_info.value.status_code == 403


def test_non_superuser_cannot_delete_or_disable_superuser(monkeypatch):
    """Delete and status changes preserve the privileged account boundary."""
    repo = _AdminRepoStub()
    monkeypatch.setattr(
        repo,
        "get_user",
        lambda _user_id: {
            "username": "root.user",
            "roles": ["superuser"],
            "is_active": True,
        },
    )
    service = _user_service(repo)

    with pytest.raises(AppError, match="Only a superuser"):
        service.delete_user(user_id="root.user")
    with pytest.raises(AppError, match="Only a superuser"):
        service.toggle_user(user_id="root.user")

    assert repo.deleted_users == []
    assert repo.updated_user is None


def test_user_can_update_only_safe_own_profile_fields():
    """Self-service profile editing cannot alter authorization or login identity."""
    repo = _AdminRepoStub()
    service = _user_service(repo)

    payload = service.update_own_profile(
        username="tester",
        payload={
            "firstname": "Updated",
            "lastname": "Name",
            "fullname": "Updated Name",
            "job_title": "Clinical Scientist",
        },
    )

    assert payload["user"]["fullname"] == "Updated Name"
    assert repo.updated_user[1]["email"] == "tester@example.com"
    assert repo.updated_user[1]["roles"] == ["admin"]
    assert repo.updated_user[1]["password"] == "hashed"

    with pytest.raises(AppError, match="cannot be edited"):
        service.update_own_profile(
            username="tester",
            payload={"roles": ["superuser"]},
        )


def test_user_can_update_only_validated_ui_settings():
    """Self-service UI settings persist independently of identity and authorization."""
    repo = _AdminRepoStub()
    service = _user_service(repo)

    payload = service.update_own_ui_settings(
        username="tester",
        payload={"analysis_layout": "modern", "analysis_modern_view_tried": True},
    )

    assert payload["ui_settings"] == {
        "theme": "auto",
        "analysis_layout": "modern",
        "sample_list_layout": "classic",
        "analysis_modern_view_tried": True,
        "sample_list_modern_view_tried": False,
        "table_page_size": 50,
    }
    assert repo.updated_user[1]["roles"] == ["admin"]
    assert repo.updated_user[1]["ui_settings"] == payload["ui_settings"]

    with pytest.raises(AppError, match="not supported"):
        service.update_own_ui_settings(
            username="tester",
            payload={"unknown_setting": "dark"},
        )

    for theme in ("dark", "light", "auto"):
        updated = service.update_own_ui_settings(username="tester", payload={"theme": theme})
        assert updated["ui_settings"]["theme"] == theme
        assert repo.updated_user[1]["roles"] == ["admin"]
    with pytest.raises(AppError, match="Invalid UI settings"):
        service.update_own_ui_settings(username="tester", payload={"theme": "invalid"})


def test_admin_role_service_create_role_normalizes_business_key(monkeypatch):
    repo = _AdminRepoStub()
    _patch_admin_stores(monkeypatch, repo)
    service = _role_service(repo)
    monkeypatch.setattr(
        "coyote3.application.accounts.roles.current_actor", lambda username: username
    )
    monkeypatch.setattr(
        admin_role_service_module,
        "normalize_managed_form_payload",
        lambda _spec, form_data: {
            "name": form_data["name"],
            "label": form_data.get("name", ""),
            "color": "#1f2937",
            "level": 9999,
            "permissions": [],
        },
    )

    payload = service.create_role(
        payload={"form_data": {"name": "Developer"}}, actor_username="actor@example.com"
    )

    assert payload["resource"] == "role"
    assert repo.created_role["role_id"] == "developer"
    assert repo.created_role["name"] == "developer"
    assert repo.created_role["level"] == 9999
    assert "version_history" not in repo.created_role


def test_admin_role_service_delete_role_removes_existing_role(monkeypatch):
    repo = _AdminRepoStub()
    _patch_admin_stores(monkeypatch, repo)
    service = _role_service(repo)

    payload = service.delete_role(role_id="admin")

    assert payload["action"] == "delete"
    assert repo.deleted_roles == ["admin"]


def test_system_installed_role_cannot_be_deleted(monkeypatch):
    repo = _AdminRepoStub()
    _patch_admin_stores(monkeypatch, repo)
    monkeypatch.setattr(
        repo,
        "get_role",
        lambda role_id: {"role_id": role_id, "system_managed": True},
    )

    with pytest.raises(AppError, match="System-installed role cannot be deleted"):
        _role_service(repo).delete_role(role_id="admin")

    assert repo.deleted_roles == []


def test_system_installed_user_cannot_be_deleted(monkeypatch):
    repo = _AdminRepoStub()
    monkeypatch.setattr(
        repo,
        "get_user",
        lambda user_id: {"username": user_id, "roles": ["superuser"], "system_managed": True},
    )

    with pytest.raises(AppError, match="System-installed user cannot be deleted"):
        _user_service(repo).delete_user(user_id="coyote3.admin", actor_is_superuser=True)

    assert repo.deleted_users == []


@pytest.mark.parametrize(
    ("service_factory", "repository_method", "delete_call", "message"),
    [
        (
            _asp_service,
            "get_panel",
            lambda service: service.delete(panel_id="demo_panel"),
            "System-installed assay panel cannot be deleted",
        ),
        (
            _aspc_service,
            "get_assay_config",
            lambda service: service.delete(assay_id="demo_panel_base_production"),
            "System-installed assay configuration cannot be deleted",
        ),
        (
            _isgl_service,
            "get_genelist",
            lambda service: service.delete(genelist_id="demo_genes"),
            "System-installed gene list cannot be deleted",
        ),
    ],
)
def test_system_installed_clinical_configuration_cannot_be_deleted(
    monkeypatch,
    service_factory,
    repository_method,
    delete_call,
    message,
):
    repo = _AdminRepoStub()
    _patch_admin_stores(monkeypatch, repo)
    monkeypatch.setattr(
        repo,
        repository_method,
        lambda resource_id: {"_id": resource_id, "system_managed": True},
    )

    with pytest.raises(AppError, match=message):
        delete_call(service_factory(repo))


def test_admin_permission_service_groups_permissions(monkeypatch):
    repo = _AdminRepoStub()
    _patch_admin_stores(monkeypatch, repo)
    service = _permission_service(repo)

    payload = service.list_permissions_payload()

    assert payload["permission_policies"][0]["permission_id"] == "sample:view"
    assert "General" in payload["grouped_permissions"]


def test_admin_permission_service_create_context_uses_backend_contract_form(monkeypatch):
    """Permission create-context should be served from the backend contract form."""
    repo = _AdminRepoStub()
    _patch_admin_stores(monkeypatch, repo)
    service = _permission_service(repo)

    payload = service.create_context_payload(actor_username="actor@example.com")

    assert payload["form"]["form_type"] == "permission"
    assert payload["form"]["fields"]["created_by"]["default"] == "actor@example.com"
    assert payload["form"]["fields"]["category"]["options"] == list(PERMISSION_CATALOG.categories)


def test_admin_permission_service_toggle_permission_sets_status(monkeypatch):
    repo = _AdminRepoStub()
    _patch_admin_stores(monkeypatch, repo)
    service = _permission_service(repo)

    payload = service.toggle_permission(permission_id="sample:view")

    assert payload["meta"]["is_active"] is False
    assert repo.updated_permission == ("sample:view", {"is_active": False})


def test_admin_panel_service_toggle_panel_sets_status(monkeypatch):
    repo = _AdminRepoStub()
    _patch_admin_stores(monkeypatch, repo)
    service = _asp_service(repo)

    payload = service.toggle(panel_id="WGS")

    assert payload["meta"]["is_active"] is True
    assert repo.updated_panel == ("WGS", {"is_active": True})


def test_admin_panel_service_create_context_populates_asp_group_dropdown(monkeypatch):
    """ASP create-context should expose the fixed assay-group vocabulary."""
    repo = _AdminRepoStub()
    _patch_admin_stores(monkeypatch, repo)
    service = _asp_service(repo)

    payload = service.create_context_payload(actor_username="actor@example.com")

    field = payload["form"]["fields"]["asp_group"]
    assert field["display_type"] == "select"
    assert field["options"] == ["hematology", "solid", "custom-group", "dna"]
    assert payload["form"]["fields"]["asp_family"]["options"] == list(ASP_FAMILY_OPTIONS)
    assert payload["form"]["fields"]["asp_category"]["options"] == list(ASP_CATEGORY_OPTIONS)
    assert payload["form"]["fields"]["platform"]["options"] == list(PLATFORM_OPTIONS)
    assert payload["form"]["fields"]["expected_files"]["category_options"] == {
        key: list(values) for key, values in SAMPLE_FILE_KEYS.items()
    }
    assert payload["form"]["fields"]["required_files"]["category_options"] == {
        key: list(values) for key, values in SAMPLE_FILE_KEYS.items()
    }


def test_admin_panel_service_edit_context_keeps_current_asp_group_selected(monkeypatch):
    """ASP edit-context should preselect the panel's current assay group."""
    repo = _AdminRepoStub()
    _patch_admin_stores(monkeypatch, repo)
    service = _asp_service(repo)

    payload = service.context_payload(panel_id="WGS")

    field = payload["form"]["fields"]["asp_group"]
    assert field["display_type"] == "select"
    assert field["default"] == payload["panel"]["asp_group"]
    assert field["options"] == ["hematology", "solid", "custom-group", "dna"]


def test_admin_genelist_service_view_context_filters_genes(monkeypatch):
    repo = _AdminRepoStub()
    _patch_admin_stores(monkeypatch, repo)
    service = _isgl_service(repo)

    payload = service.view_context_payload(genelist_id="GL1", assay="WGS")

    assert payload["filtered_genes"] == ["TP53"]
    assert payload["panel_germline_genes"] == ["BRCA1"]


def test_admin_genelist_form_filters_asps_by_selected_groups(monkeypatch):
    """ISGL forms expose active ASP choices under their owning assay groups."""
    repo = _AdminRepoStub()
    _patch_admin_stores(monkeypatch, repo)
    service = _isgl_service(repo)
    service.assay_panel_repository.get_all_asps = lambda is_active=None: [
        {"asp_id": "hema_gmsv1", "display_name": "Hematology GMSv1", "asp_group": "hematology"},
        {"asp_id": "demo-solid_gmsv3", "display_name": "Solid DNA GMSv3", "asp_group": "solid"},
    ]

    payload = service.create_context_payload(actor_username="actor@example.com")
    form = payload["form"]

    assert "diagnosis_id" not in form["fields"]
    assert form["fields"]["diagnosis"]["label"] == "Diagnoses"
    assert form["fields"]["asp_ids"]["options_by_field"] == {
        "field": "asp_groups",
        "values": {
            "hematology": [
                {
                    "value": "hema_gmsv1",
                    "label": "Hematology GMSv1",
                    "category": "hematology",
                }
            ],
            "solid": [
                {
                    "value": "demo-solid_gmsv3",
                    "label": "Solid DNA GMSv3",
                    "category": "solid",
                }
            ],
        },
    }


def test_admin_genelist_rejects_asp_outside_selected_groups(monkeypatch):
    """Direct API writes cannot bypass the dependent ASP-group selection."""
    repo = _AdminRepoStub()
    _patch_admin_stores(monkeypatch, repo)
    service = _isgl_service(repo)
    service.assay_panel_repository.get_all_asps = lambda is_active=None: [
        {"asp_id": "hema_gmsv1", "asp_group": "hematology"},
        {"asp_id": "demo-solid_gmsv3", "asp_group": "solid"},
    ]

    with pytest.raises(AppError) as exc_info:
        service.create(
            payload={
                "config": {
                    "isgl_id": "missing",
                    "name": "Solid scope",
                    "displayname": "Solid scope",
                    "list_type": ["snv"],
                    "asp_groups": ["solid"],
                    "asp_ids": ["hema_gmsv1"],
                }
            }
        )

    assert exc_info.value.status_code == 400
    assert "selected assay groups" in exc_info.value.message


def test_admin_aspc_create_context_scopes_optional_genelist_fields(monkeypatch):
    """ASPC forms expose optional ISGL choices scoped to the selected ASP."""
    repo = _AdminRepoStub()
    _patch_admin_stores(monkeypatch, repo)
    service = _aspc_service(repo)

    payload = service.create_context_payload(category="DNA", actor_username="actor@example.com")
    form = payload["form"]
    analysis_options = form["fields"]["analysis_types"]["options"]
    analysis_options_by_asp = form["fields"]["analysis_types"]["options_by_field"]
    diagnosis_options_by_asp = form["fields"]["diagnosis_id"]["options_by_field"]
    filter_groups = form["fields"]["filters"]["groups"]
    reporting_groups = form["fields"]["reporting"]["groups"]
    filter_keys = {field["key"] for group in filter_groups for field in group.get("fields", [])}
    report_section_options = reporting_groups[0]["fields"][0]["options"]
    reporting_field_keys = {
        field["key"] for group in reporting_groups for field in group.get("fields", [])
    }

    assert "TMB" in analysis_options
    assert "PGX" in analysis_options
    assert analysis_options_by_asp["field"] == "asp_id"
    assert "SNV" in analysis_options_by_asp["values"]["wgs"]
    assert diagnosis_options_by_asp["field"] == "asp_id"
    assert diagnosis_options_by_asp["values"]["wgs"][0]["value"] == "base"
    assert "somatic.snv.snvlists" in filter_keys
    for intent in ("somatic", "germline"):
        flag_field = next(
            field
            for group in filter_groups
            for field in group.get("fields", [])
            if field["key"] == f"{intent}.snv.exclude_flags"
        )
        assert "WARN_NOVAR" in flag_field["options"]
        assert "PASS" in flag_field["options"]
    assert "somatic.cnv.cnvlists" in filter_keys
    assert "somatic.fusion.fusionlists" not in filter_keys
    assert "somatic.translocation.fusionlists" in filter_keys
    snv_list_field = next(
        field
        for group in filter_groups
        for field in group.get("fields", [])
        if field["key"] == "somatic.snv.snvlists"
    )
    assert snv_list_field["options_by_field"]["field"] == "asp_id"
    assert snv_list_field["options_by_field"]["values"]["wgs"] == []
    assert "TMB" in report_section_options
    assert "PGX" in report_section_options
    assert "report_sections" in reporting_field_keys
    assert "analysis" not in reporting_field_keys
    assert "language" in reporting_field_keys
    assert "clinical_rule_set_id" not in reporting_field_keys


def test_admin_aspc_analysis_types_follow_the_asp_sequencing_family():
    """Targeted RNA panels reject WTS-only capabilities while WTS accepts them."""
    with pytest.raises(AppError) as exc_info:
        AspcService._validate_analysis_types_for_panel(
            {"analysis_types": ["FUSION", "EXPRESSION"]},
            {"asp_family": "panel-rna"},
        )

    assert exc_info.value.status_code == 400
    assert "EXPRESSION" in exc_info.value.message

    AspcService._validate_analysis_types_for_panel(
        {"analysis_types": ["FUSION", "EXPRESSION", "CLASSIFICATION", "QC"]},
        {
            "asp_family": "wts",
            "asp_category": "rna",
            "expected_files": ["fusion_files", "expression_path", "classification_path", "qc"],
        },
    )

    assert AspcService._analysis_types_for_panel(
        {"asp_family": "panel-rna", "expected_files": ["fusion_files", "qc"]}, category="RNA"
    ) == [
        "FUSION",
        "QC",
    ]
    assert "EXPRESSION" in AspcService._analysis_types_for_panel(
        {"asp_family": "wts", "expected_files": ["expression_path"]}, category="RNA"
    )


def test_admin_aspc_service_create_rejects_duplicate(monkeypatch):
    repo = _AdminRepoStub()
    _patch_admin_stores(monkeypatch, repo)
    service = _aspc_service(repo)

    with pytest.raises(AppError) as exc:
        service.create(
            payload={
                "config": {"asp_id": "wgs", "environment": "production", "diagnosis_id": "base"}
            }
        )

    assert exc.value.status_code == 409


def test_admin_sample_service_update_restores_ids(monkeypatch):
    repo = _AdminRepoStub()
    _patch_admin_stores(monkeypatch, repo)
    service = _resource_sample_service(repo)
    monkeypatch.setattr(
        "coyote3.application.resources.sample.current_actor", lambda username: username
    )
    monkeypatch.setattr(
        "coyote3.application.resources.sample.utc_now", lambda: datetime.now(timezone.utc)
    )
    payload = service.update(
        sample_id="S1",
        payload={
            "sample": {
                "name": "CASE_1",
                "asp_id": "hema_gmsv1",
                "diagnosis_id": "base",
                "environment": "production",
                "case_id": "CASE_1",
                "sample_no": 1,
                "asp_family": "panel-dna",
                "asp_category": "dna",
                "pipeline": "test_pipeline",
                "pipeline_version": "1.0",
                "files": {"vcf_files": {"path": "/data/test.vcf"}},
                "field": "value",
            }
        },
        actor_username="actor@example.com",
    )

    assert payload["resource"] == "sample"
    assert payload["resource_id"] == "S1"
    assert payload["meta"]["sample_name"] == "CASE_1"
    assert payload["meta"]["sample_oid"] == "S1"
    assert repo.updated_sample_doc[0] == "S1"
