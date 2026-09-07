"""Load center-owned public contact information."""

from __future__ import annotations

import tomllib
from pathlib import Path
from typing import Any

from api.config.application_metadata import APPLICATION_DESCRIPTION, CODEBASE_LINKS
from api.config.paths import REPO_ROOT


def normalize_url_prefix(value: str | None) -> str:
    """Normalize an externally mounted URL prefix such as ``SCRIPT_NAME``."""
    raw = (value or "").strip()
    return "" if not raw or raw == "/" else "/" + raw.strip("/")


def join_public_url(base_url: str, script_name: str, suffix: str = "") -> str:
    """Join a public origin, mount prefix, and browser-facing suffix."""
    base = base_url.strip().rstrip("/")
    if not base:
        return ""
    normalized_suffix = "/" + suffix.strip("/") if suffix.strip("/") else ""
    trailing = "/" if suffix.endswith("/") else ""
    return f"{base}{normalize_url_prefix(script_name)}{normalized_suffix}{trailing}"


def _application_links() -> list[dict[str, str]]:
    """Return repository-owned links shown on public pages."""
    return [
        {
            "label": "User documentation",
            "url": "/docs-site/",
            "description": "Clinical user guide and operational documentation.",
            "icon": "docs",
        },
        {
            "label": "Assay catalog",
            "url": "/public/catalog",
            "description": "Public assay, panel, and gene-list reference.",
            "icon": "catalog",
        },
        {
            "label": "Project repository",
            "url": CODEBASE_LINKS["repository_url"],
            "description": "Source repository, release history, and technical project context.",
            "icon": "github",
        },
        {
            "label": "Report a Bug",
            "url": CODEBASE_LINKS["bug_report_url"],
            "description": "Report an application defect or reproducible malfunction.",
            "icon": "bug",
        },
        {
            "label": "Request a Feature",
            "url": CODEBASE_LINKS["feature_request_url"],
            "description": "Suggest a product improvement or workflow enhancement.",
            "icon": "feature",
        },
        {
            "label": "Support",
            "url": CODEBASE_LINKS["support_request_url"],
            "description": "Ask for help with setup, usage, access, or operational behavior.",
            "icon": "issue",
        },
    ]


def application_integration_links(config: dict[str, Any]) -> list[dict[str, str]]:
    """Return configured external clinical tools suitable for the About page."""
    candidates = (
        ("GENS", "GENS copy-number and BAF visualization.", "GENS_URI", "external"),
        ("IGV", "Integrative Genomics Viewer for alignment review.", "IGV_URI", "external"),
        ("OncoKB Public", "Public cancer knowledgebase.", "ONCOKB_BASE_URL", "external"),
        (
            "ClinPGx Public",
            "Public pharmacogenomics knowledgebase.",
            "CLINPGX_BASE_URL",
            "external",
        ),
    )
    return [
        {
            "label": label,
            "description": description,
            "url": str(config.get(key) or "").strip(),
            "icon": icon,
        }
        for label, description, key, icon in candidates
        if str(config.get(key) or "").strip()
    ]


def load_contact_config(
    config_path: str | Path,
    *,
    organization_name: str,
    public_base_url: str,
    script_name: str,
) -> dict[str, Any]:
    """Load center contacts and combine them with application-owned metadata."""
    path_obj = Path(config_path)
    if not path_obj.is_absolute():
        path_obj = (REPO_ROOT / path_obj).resolve()
    if not path_obj.exists():
        raise RuntimeError(f"CONTACT_CONFIG_PATH does not exist: {path_obj}")
    with path_obj.open("rb") as handle:
        raw = tomllib.load(handle)

    organization = dict(raw.get("organization") or {})
    organization.update(
        {
            "name": organization_name,
            "description": APPLICATION_DESCRIPTION,
            "site_name": "Coyote3",
        }
    )
    support = dict(raw.get("support") or {})
    web_app_base_url = join_public_url(public_base_url, script_name, "/")
    help_center_url = join_public_url(public_base_url, script_name, "/docs-site/")
    if web_app_base_url:
        support.setdefault("web_app_base_url", web_app_base_url)
    if help_center_url:
        support.setdefault("help_center_url", help_center_url)

    return {
        "organization": organization,
        "support": support,
        "codebase": dict(CODEBASE_LINKS),
        "contacts": list(raw.get("contacts") or []),
        "links": _application_links(),
        "hours": list(raw.get("hours") or []),
        "meta": {"source": str(path_obj), "format": "toml"},
    }
