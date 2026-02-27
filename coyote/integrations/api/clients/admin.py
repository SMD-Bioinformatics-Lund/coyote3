"""Admin API client mixin methods."""

from __future__ import annotations

from typing import Any

from coyote.integrations.api.base import ApiPayload


class AdminApiClientMixin:
    def create_admin_permission(
        self,
        schema_id: str | None,
        form_data: dict[str, Any],
        headers: dict[str, str] | None = None,
    ) -> ApiPayload:
        payload = self._post(
            "/api/v1/admin/permissions/create",
            headers=headers,
            json_body={"schema_id": schema_id, "form_data": form_data},
        )
        return payload

    def get_admin_permissions(
        self,
        headers: dict[str, str] | None = None,
    ) -> ApiPayload:
        payload = self._get("/api/v1/admin/permissions", headers=headers)
        return payload

    def get_admin_permission_create_context(
        self,
        schema_id: str | None = None,
        headers: dict[str, str] | None = None,
    ) -> ApiPayload:
        params = {"schema_id": schema_id} if schema_id else None
        payload = self._get("/api/v1/admin/permissions/create_context", headers=headers, params=params)
        return payload

    def get_admin_permission_context(
        self,
        perm_id: str,
        headers: dict[str, str] | None = None,
    ) -> ApiPayload:
        payload = self._get(f"/api/v1/admin/permissions/{perm_id}/context", headers=headers)
        return payload

    def update_admin_permission(
        self,
        perm_id: str,
        form_data: dict[str, Any],
        headers: dict[str, str] | None = None,
    ) -> ApiPayload:
        payload = self._post(
            f"/api/v1/admin/permissions/{perm_id}/update",
            headers=headers,
            json_body={"form_data": form_data},
        )
        return payload

    def toggle_admin_permission(
        self,
        perm_id: str,
        headers: dict[str, str] | None = None,
    ) -> ApiPayload:
        payload = self._post(f"/api/v1/admin/permissions/{perm_id}/toggle", headers=headers)
        return payload

    def delete_admin_permission(
        self,
        perm_id: str,
        headers: dict[str, str] | None = None,
    ) -> ApiPayload:
        payload = self._post(f"/api/v1/admin/permissions/{perm_id}/delete", headers=headers)
        return payload

    def create_admin_schema(
        self,
        schema_doc: dict[str, Any],
        headers: dict[str, str] | None = None,
    ) -> ApiPayload:
        payload = self._post(
            "/api/v1/admin/schemas/create",
            headers=headers,
            json_body={"schema": schema_doc},
        )
        return payload

    def get_admin_schemas(
        self,
        headers: dict[str, str] | None = None,
    ) -> ApiPayload:
        payload = self._get("/api/v1/admin/schemas", headers=headers)
        return payload

    def get_admin_schema_context(
        self,
        schema_id: str,
        headers: dict[str, str] | None = None,
    ) -> ApiPayload:
        payload = self._get(f"/api/v1/admin/schemas/{schema_id}/context", headers=headers)
        return payload

    def update_admin_schema(
        self,
        schema_id: str,
        schema_doc: dict[str, Any],
        headers: dict[str, str] | None = None,
    ) -> ApiPayload:
        payload = self._post(
            f"/api/v1/admin/schemas/{schema_id}/update",
            headers=headers,
            json_body={"schema": schema_doc},
        )
        return payload

    def toggle_admin_schema(
        self,
        schema_id: str,
        headers: dict[str, str] | None = None,
    ) -> ApiPayload:
        payload = self._post(f"/api/v1/admin/schemas/{schema_id}/toggle", headers=headers)
        return payload

    def delete_admin_schema(
        self,
        schema_id: str,
        headers: dict[str, str] | None = None,
    ) -> ApiPayload:
        payload = self._post(f"/api/v1/admin/schemas/{schema_id}/delete", headers=headers)
        return payload

    def create_admin_role(
        self,
        schema_id: str | None,
        form_data: dict[str, Any],
        headers: dict[str, str] | None = None,
    ) -> ApiPayload:
        payload = self._post(
            "/api/v1/admin/roles/create",
            headers=headers,
            json_body={"schema_id": schema_id, "form_data": form_data},
        )
        return payload

    def get_admin_roles(
        self,
        headers: dict[str, str] | None = None,
    ) -> ApiPayload:
        payload = self._get("/api/v1/admin/roles", headers=headers)
        return payload

    def get_admin_role_create_context(
        self,
        schema_id: str | None = None,
        headers: dict[str, str] | None = None,
    ) -> ApiPayload:
        params = {"schema_id": schema_id} if schema_id else None
        payload = self._get("/api/v1/admin/roles/create_context", headers=headers, params=params)
        return payload

    def get_admin_role_context(
        self,
        role_id: str,
        headers: dict[str, str] | None = None,
    ) -> ApiPayload:
        payload = self._get(f"/api/v1/admin/roles/{role_id}/context", headers=headers)
        return payload

    def update_admin_role(
        self,
        role_id: str,
        form_data: dict[str, Any],
        headers: dict[str, str] | None = None,
    ) -> ApiPayload:
        payload = self._post(
            f"/api/v1/admin/roles/{role_id}/update",
            headers=headers,
            json_body={"form_data": form_data},
        )
        return payload

    def toggle_admin_role(
        self,
        role_id: str,
        headers: dict[str, str] | None = None,
    ) -> ApiPayload:
        payload = self._post(f"/api/v1/admin/roles/{role_id}/toggle", headers=headers)
        return payload

    def delete_admin_role(
        self,
        role_id: str,
        headers: dict[str, str] | None = None,
    ) -> ApiPayload:
        payload = self._post(f"/api/v1/admin/roles/{role_id}/delete", headers=headers)
        return payload

    def create_admin_user(
        self,
        schema_id: str | None,
        form_data: dict[str, Any],
        headers: dict[str, str] | None = None,
    ) -> ApiPayload:
        payload = self._post(
            "/api/v1/admin/users/create",
            headers=headers,
            json_body={"schema_id": schema_id, "form_data": form_data},
        )
        return payload

    def get_admin_users(
        self,
        headers: dict[str, str] | None = None,
    ) -> ApiPayload:
        payload = self._get("/api/v1/admin/users", headers=headers)
        return payload

    def get_admin_user_create_context(
        self,
        schema_id: str | None = None,
        headers: dict[str, str] | None = None,
    ) -> ApiPayload:
        params = {"schema_id": schema_id} if schema_id else None
        payload = self._get("/api/v1/admin/users/create_context", headers=headers, params=params)
        return payload

    def get_admin_user_context(
        self,
        user_id: str,
        headers: dict[str, str] | None = None,
    ) -> ApiPayload:
        payload = self._get(f"/api/v1/admin/users/{user_id}/context", headers=headers)
        return payload

    def update_admin_user(
        self,
        user_id: str,
        form_data: dict[str, Any],
        headers: dict[str, str] | None = None,
    ) -> ApiPayload:
        payload = self._post(
            f"/api/v1/admin/users/{user_id}/update",
            headers=headers,
            json_body={"form_data": form_data},
        )
        return payload

    def delete_admin_user(
        self,
        user_id: str,
        headers: dict[str, str] | None = None,
    ) -> ApiPayload:
        payload = self._post(f"/api/v1/admin/users/{user_id}/delete", headers=headers)
        return payload

    def toggle_admin_user(
        self,
        user_id: str,
        headers: dict[str, str] | None = None,
    ) -> ApiPayload:
        payload = self._post(f"/api/v1/admin/users/{user_id}/toggle", headers=headers)
        return payload

    def validate_admin_username(
        self,
        username: str,
        headers: dict[str, str] | None = None,
    ) -> bool:
        payload = self._post(
            "/api/v1/admin/users/validate_username",
            headers=headers,
            json_body={"username": username},
        )
        return bool(payload.get("exists", False))

    def validate_admin_email(
        self,
        email: str,
        headers: dict[str, str] | None = None,
    ) -> bool:
        payload = self._post(
            "/api/v1/admin/users/validate_email",
            headers=headers,
            json_body={"email": email},
        )
        return bool(payload.get("exists", False))

    def create_admin_asp(
        self,
        config: dict[str, Any],
        headers: dict[str, str] | None = None,
    ) -> ApiPayload:
        payload = self._post(
            "/api/v1/admin/asp/create",
            headers=headers,
            json_body={"config": config},
        )
        return payload

    def get_admin_asp(
        self,
        headers: dict[str, str] | None = None,
    ) -> ApiPayload:
        payload = self._get("/api/v1/admin/asp", headers=headers)
        return payload

    def get_admin_asp_create_context(
        self,
        schema_id: str | None = None,
        headers: dict[str, str] | None = None,
    ) -> ApiPayload:
        params = {"schema_id": schema_id} if schema_id else None
        payload = self._get("/api/v1/admin/asp/create_context", headers=headers, params=params)
        return payload

    def get_admin_asp_context(
        self,
        assay_panel_id: str,
        headers: dict[str, str] | None = None,
    ) -> ApiPayload:
        payload = self._get(f"/api/v1/admin/asp/{assay_panel_id}/context", headers=headers)
        return payload

    def update_admin_asp(
        self,
        assay_panel_id: str,
        config: dict[str, Any],
        headers: dict[str, str] | None = None,
    ) -> ApiPayload:
        payload = self._post(
            f"/api/v1/admin/asp/{assay_panel_id}/update",
            headers=headers,
            json_body={"config": config},
        )
        return payload

    def toggle_admin_asp(
        self,
        assay_panel_id: str,
        headers: dict[str, str] | None = None,
    ) -> ApiPayload:
        payload = self._post(f"/api/v1/admin/asp/{assay_panel_id}/toggle", headers=headers)
        return payload

    def delete_admin_asp(
        self,
        assay_panel_id: str,
        headers: dict[str, str] | None = None,
    ) -> ApiPayload:
        payload = self._post(f"/api/v1/admin/asp/{assay_panel_id}/delete", headers=headers)
        return payload

    def create_admin_genelist(
        self,
        config: dict[str, Any],
        headers: dict[str, str] | None = None,
    ) -> ApiPayload:
        payload = self._post(
            "/api/v1/admin/genelists/create",
            headers=headers,
            json_body={"config": config},
        )
        return payload

    def get_admin_genelists(
        self,
        headers: dict[str, str] | None = None,
    ) -> ApiPayload:
        payload = self._get("/api/v1/admin/genelists", headers=headers)
        return payload

    def get_admin_genelist_create_context(
        self,
        schema_id: str | None = None,
        headers: dict[str, str] | None = None,
    ) -> ApiPayload:
        params = {"schema_id": schema_id} if schema_id else None
        payload = self._get("/api/v1/admin/genelists/create_context", headers=headers, params=params)
        return payload

    def get_admin_genelist_context(
        self,
        genelist_id: str,
        headers: dict[str, str] | None = None,
    ) -> ApiPayload:
        payload = self._get(f"/api/v1/admin/genelists/{genelist_id}/context", headers=headers)
        return payload

    def get_admin_genelist_view_context(
        self,
        genelist_id: str,
        selected_assay: str | None = None,
        headers: dict[str, str] | None = None,
    ) -> ApiPayload:
        params = {"assay": selected_assay} if selected_assay else None
        payload = self._get(
            f"/api/v1/admin/genelists/{genelist_id}/view_context",
            headers=headers,
            params=params,
        )
        return payload

    def update_admin_genelist(
        self,
        genelist_id: str,
        config: dict[str, Any],
        headers: dict[str, str] | None = None,
    ) -> ApiPayload:
        payload = self._post(
            f"/api/v1/admin/genelists/{genelist_id}/update",
            headers=headers,
            json_body={"config": config},
        )
        return payload

    def toggle_admin_genelist(
        self,
        genelist_id: str,
        headers: dict[str, str] | None = None,
    ) -> ApiPayload:
        payload = self._post(f"/api/v1/admin/genelists/{genelist_id}/toggle", headers=headers)
        return payload

    def delete_admin_genelist(
        self,
        genelist_id: str,
        headers: dict[str, str] | None = None,
    ) -> ApiPayload:
        payload = self._post(f"/api/v1/admin/genelists/{genelist_id}/delete", headers=headers)
        return payload

    def update_admin_sample(
        self,
        sample_id: str,
        sample: dict[str, Any],
        headers: dict[str, str] | None = None,
    ) -> ApiPayload:
        payload = self._post(
            f"/api/v1/admin/samples/{sample_id}/update",
            headers=headers,
            json_body={"sample": sample},
        )
        return payload

    def get_admin_samples(
        self,
        search: str = "",
        headers: dict[str, str] | None = None,
    ) -> ApiPayload:
        payload = self._get(
            "/api/v1/admin/samples",
            headers=headers,
            params={"search": search} if search else None,
        )
        return payload

    def get_admin_sample_context(
        self,
        sample_id: str,
        headers: dict[str, str] | None = None,
    ) -> ApiPayload:
        payload = self._get(f"/api/v1/admin/samples/{sample_id}/context", headers=headers)
        return payload

    def delete_admin_sample(
        self,
        sample_id: str,
        headers: dict[str, str] | None = None,
    ) -> ApiPayload:
        payload = self._post(f"/api/v1/admin/samples/{sample_id}/delete", headers=headers)
        return payload

    def create_admin_aspc(
        self,
        config: dict[str, Any],
        headers: dict[str, str] | None = None,
    ) -> ApiPayload:
        payload = self._post(
            "/api/v1/admin/aspc/create",
            headers=headers,
            json_body={"config": config},
        )
        return payload

    def get_admin_aspc(
        self,
        headers: dict[str, str] | None = None,
    ) -> ApiPayload:
        payload = self._get("/api/v1/admin/aspc", headers=headers)
        return payload

    def get_admin_aspc_create_context(
        self,
        category: str,
        schema_id: str | None = None,
        headers: dict[str, str] | None = None,
    ) -> ApiPayload:
        params: dict[str, Any] = {"category": category}
        if schema_id:
            params["schema_id"] = schema_id
        payload = self._get("/api/v1/admin/aspc/create_context", headers=headers, params=params)
        return payload

    def get_admin_aspc_context(
        self,
        assay_id: str,
        headers: dict[str, str] | None = None,
    ) -> ApiPayload:
        payload = self._get(f"/api/v1/admin/aspc/{assay_id}/context", headers=headers)
        return payload

    def update_admin_aspc(
        self,
        assay_id: str,
        config: dict[str, Any],
        headers: dict[str, str] | None = None,
    ) -> ApiPayload:
        payload = self._post(
            f"/api/v1/admin/aspc/{assay_id}/update",
            headers=headers,
            json_body={"config": config},
        )
        return payload

    def toggle_admin_aspc(
        self,
        assay_id: str,
        headers: dict[str, str] | None = None,
    ) -> ApiPayload:
        payload = self._post(f"/api/v1/admin/aspc/{assay_id}/toggle", headers=headers)
        return payload

    def delete_admin_aspc(
        self,
        assay_id: str,
        headers: dict[str, str] | None = None,
    ) -> ApiPayload:
        payload = self._post(f"/api/v1/admin/aspc/{assay_id}/delete", headers=headers)
        return payload

