"""Admin landing-page routes and dashboard card configuration."""

from typing import Any

from flask import current_app, render_template, url_for
from flask_login import login_required

from coyote.blueprints.admin import admin_bp

_ADMIN_CARDS: list[dict[str, Any]] = [
    {
        "endpoint": "admin_bp.all_samples",
        "permission": "sample:list:global",
        "min_role": "developer",
        "min_level": 9999,
        "icon": "square-3-stack-3d.svg",
        "title": "Manage Samples",
        "desc": "Delete samples, purge data, etc.",
        "category": "Samples",
        "color": "blue",
    },
    {
        "endpoint": "admin_bp.manage_users",
        "permission": "user:list",
        "min_role": "admin",
        "min_level": 99999,
        "icon": "users.svg",
        "title": "Manage Users",
        "desc": "Add, update, remove users",
        "category": "Users",
        "color": "yellow",
    },
    {
        "endpoint": "admin_bp.create_user",
        "permission": "user:create",
        "min_role": "admin",
        "min_level": 99999,
        "icon": "user-plus.svg",
        "title": "New User",
        "desc": "Create new users for the platform",
        "category": "Users",
        "color": "yellow",
    },
    {
        "endpoint": "admin_bp.list_roles",
        "permission": "role:list",
        "min_role": "admin",
        "min_level": 99999,
        "icon": "user-circle.svg",
        "title": "Manage Roles",
        "desc": "Adjust role policies for users",
        "category": "Roles",
        "color": "pink",
    },
    {
        "endpoint": "admin_bp.create_role",
        "permission": "role:create",
        "min_role": "admin",
        "min_level": 99999,
        "icon": "user-circle.svg",
        "title": "New Role Policy",
        "desc": "Add new role policy to system",
        "category": "Roles",
        "color": "pink",
    },
    {
        "endpoint": "admin_bp.list_permissions",
        "permission": "permission.policy:list",
        "min_role": "admin",
        "min_level": 99999,
        "icon": "key.svg",
        "title": "Manage Permissions",
        "desc": "Adjust permission policies for users",
        "category": "Permissions",
        "color": "orange",
    },
    {
        "endpoint": "admin_bp.create_permission",
        "permission": "permission.policy:create",
        "min_role": "admin",
        "min_level": 99999,
        "icon": "key.svg",
        "title": "New Permission Policy",
        "desc": "Add new permission policy to system",
        "category": "Permissions",
        "color": "orange",
    },
    {
        "endpoint": "admin_bp.manage_assay_panels",
        "permission": "assay.panel:list",
        "min_role": "manager",
        "min_level": 99,
        "icon": "list-bullet.svg",
        "title": "Manage ASPs",
        "desc": "Manage assay specific asp",
        "category": "ASP",
        "color": "red",
    },
    {
        "endpoint": "admin_bp.create_assay_panel",
        "permission": "assay.panel:create",
        "min_role": "manager",
        "min_level": 99,
        "icon": "document-plus.svg",
        "title": "New ASP",
        "desc": "Add new assay specific panel to system",
        "category": "ASP",
        "color": "red",
    },
    {
        "endpoint": "admin_bp.assay_configs",
        "permission": "assay.config:list",
        "min_role": "manager",
        "min_level": 99,
        "icon": "document-duplicate.svg",
        "title": "Manage ASPCs",
        "desc": "Adjust assay/panel specific configuration",
        "category": "ASPC",
        "color": "green",
    },
    {
        "endpoint": "admin_bp.create_dna_assay_config",
        "permission": "assay.config:create",
        "min_role": "manager",
        "min_level": 99,
        "icon": "document-plus.svg",
        "title": "New DNA ASPC",
        "desc": "Add new DNA based assay specific panel configuration to system",
        "category": "ASPC",
        "color": "green",
    },
    {
        "endpoint": "admin_bp.create_rna_assay_config",
        "permission": "assay.config:create",
        "min_role": "manager",
        "min_level": 99,
        "icon": "document-plus.svg",
        "title": "New RNA ASPC",
        "desc": "Add new RNA based assay specific panel configuration to system",
        "category": "ASPC",
        "color": "green",
    },
    {
        "endpoint": "admin_bp.manage_genelists",
        "permission": "gene_list.insilico:list",
        "min_role": "manager",
        "min_level": 99,
        "icon": "list-bullet.svg",
        "title": "Manage ISGLs",
        "desc": "Manage in-silico gene lists",
        "category": "GeneLists",
        "color": "indigo",
    },
    {
        "endpoint": "admin_bp.create_genelist",
        "permission": "gene_list.insilico:create",
        "min_role": "manager",
        "min_level": 99,
        "icon": "document-plus.svg",
        "title": "New ISGL",
        "desc": "Add new in-silico gene list to system",
        "category": "GeneLists",
        "color": "indigo",
    },
    {
        "endpoint": "admin_bp.audit",
        "permission": "audit_log:view",
        "min_role": "superuser",
        "min_level": 1000000,
        "superuser_only": True,
        "icon": "newspaper.svg",
        "title": "Audit Logs",
        "desc": "Track changes and activities",
        "category": "Audit",
        "color": "brown",
    },
    {
        "endpoint": "admin_bp.ingest_workspace",
        "permission": "sample:edit:own",
        "min_role": "developer",
        "min_level": 9999,
        "icon": "arrow-up-tray.svg",
        "title": "Data Ingestion",
        "desc": "Upload sample bundles and manage collection data",
        "category": "Ingestion",
        "color": "purple",
    },
]


def build_admin_cards() -> list[dict[str, Any]]:
    """Build the canonical admin navigation cards with endpoint availability metadata."""
    registered = set(current_app.view_functions.keys())
    cards: list[dict[str, Any]] = []
    for item in _ADMIN_CARDS:
        card = dict(item)
        endpoint = str(card["endpoint"])
        is_available = endpoint in registered
        card["available"] = is_available
        card["url"] = url_for(endpoint) if is_available else "#"
        cards.append(card)
    return cards


@admin_bp.app_context_processor
def inject_admin_navigation_cards() -> dict[str, Any]:
    """Expose canonical admin navigation cards to admin templates."""
    return {"admin_navigation_cards": build_admin_cards()}


@admin_bp.route("/")
@login_required
def admin_home() -> Any:
    """Render the admin landing page and available governance cards.

    Returns:
        The rendered admin landing page response.
    """
    return render_template("admin_home.html", cards=build_admin_cards())
