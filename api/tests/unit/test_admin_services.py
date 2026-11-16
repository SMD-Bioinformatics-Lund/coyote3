"""Unit tests for admin workflow services."""

from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace

import coyote.application.accounts.permissions as admin_permission_service_module
import coyote.application.accounts.roles as admin_role_service_module
import coyote.application.accounts.users as admin_user_service_module
import coyote.application.resources.asp as admin_asp_service_module
import coyote.application.resources.aspc as admin_aspc_service_module
import coyote.application.resources.isgl as admin_isgl_service_module
import coyote.application.resources.sample as admin_resource_service_module
import pytest
from coyote.application.accounts.users import UserManagementService
from coyote.contracts.operations import OperationResult
from coyote.domain.exceptions import AppError
from coyote_api.security.passwords import hash_password
from coyote_mongo.repositories.assay_configurations import ASPConfigRepository


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
        password_hasher=hash_password,
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
        "coyote.application.accounts.users.current_actor", lambda username: username
    )
    monkeypatch.setattr(
        "coyote.application.accounts.users.utc_now", lambda: datetime.now(timezone.utc)
    )
    service = UserManagementService(
        password_token_issuer=lambda **_: {},
        user_change_notifier=lambda **_: {},
        user_repository=service.user_repository,
        roles_repository=service.roles_repository,
        permissions_repository=service.permissions_repository,
        assay_panel_repository=service.assay_panel_repository,
        password_hasher=hash_password,
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
        "analysis_layout": "modern",
        "analysis_modern_view_tried": True,
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


def test_system_installed_user_cannot_be_deleted(monkeypatch):
    repo = _AdminRepoStub()
    monkeypatch.setattr(
        repo,
        "get_user",
        lambda user_id: {"username": user_id, "roles": ["superuser"], "system_managed": True},
    )

    with pytest.raises(AppError, match="System-installed user cannot be deleted"):
        _user_service(repo).delete_user(user_id="coyote4.admin", actor_is_superuser=True)

    assert repo.deleted_users == []
