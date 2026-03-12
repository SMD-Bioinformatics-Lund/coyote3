"""Admin landing-page routes and dashboard card configuration."""

from typing import Any

from flask import current_app, render_template, url_for
from flask_login import login_required

from coyote.blueprints.admin import admin_bp

_ADMIN_CARDS: list[dict[str, Any]] = [
    {
        "endpoint": "admin_bp.all_samples",
        "permission": "view_sample_global",
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
        "permission": "view_users",
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
        "permission": "create_user",
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
        "permission": "view_role",
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
        "permission": "create_role",
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
        "permission": "view_permission_policy",
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
        "permission": "create_permission_policy",
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
        "permission": "view_asp",
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
        "permission": "create_asp",
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
        "permission": "view_aspc",
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
        "permission": "create_aspc",
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
        "permission": "create_aspc",
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
        "permission": "view_isgl",
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
        "permission": "create_isgl",
        "min_role": "manager",
        "min_level": 99,
        "icon": "document-plus.svg",
        "title": "New ISGL",
        "desc": "Add new in-silico gene list to system",
        "category": "GeneLists",
        "color": "indigo",
    },
    {
        "endpoint": "admin_bp.schemas",
        "permission": "view_schema",
        "min_role": "developer",
        "min_level": 9999,
        "icon": "rectangle-stack.svg",
        "title": "Manage Schemas",
        "desc": "Adjust master schema configurations",
        "category": "Schemas",
        "color": "purple",
    },
    {
        "endpoint": "admin_bp.create_schema",
        "permission": "create_schema",
        "min_role": "developer",
        "min_level": 9999,
        "icon": "document-check.svg",
        "title": "New Schema",
        "desc": "Create a new master schema configuration",
        "category": "Schemas",
        "color": "purple",
    },
    {
        "endpoint": "admin_bp.audit",
        "permission": "view_audit_logs",
        "min_role": "admin",
        "min_level": 99999,
        "icon": "newspaper.svg",
        "title": "Audit Logs",
        "desc": "Track changes and activities",
        "category": "Audit",
        "color": "brown",
    },
]


@admin_bp.route("/")
@login_required
def admin_home() -> Any:
    """Render the admin landing page with the currently available admin cards."""
    registered = set(current_app.view_functions.keys())
    cards: list[dict[str, Any]] = []
    for item in _ADMIN_CARDS:
        card = dict(item)
        endpoint = str(card["endpoint"])
        is_available = endpoint in registered
        card["available"] = is_available
        card["url"] = url_for(endpoint) if is_available else "#"
        cards.append(card)
    return render_template("admin_home.html", cards=cards)
