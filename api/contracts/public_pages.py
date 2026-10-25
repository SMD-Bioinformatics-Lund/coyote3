"""Public product and contact-page HTTP response contracts."""

from typing import Any

from pydantic import BaseModel


class PublicContactPayload(BaseModel):
    """Represent center-owned public contact and support metadata."""

    organization: dict[str, Any]
    support: dict[str, Any]
    codebase: dict[str, Any] = {}
    contacts: list[dict[str, Any]]
    links: list[dict[str, Any]]
    hours: list[dict[str, Any]]
    meta: dict[str, Any] = {}


class PublicAboutPayload(PublicContactPayload):
    """Represent public application, organization, and reference metadata."""

    application: dict[str, Any]
    references: dict[str, Any]
    software: dict[str, Any]
    databases: dict[str, Any]
    software_links: list[dict[str, Any]] = []
    knowledgebase_status: dict[str, Any] = {}
