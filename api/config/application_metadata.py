"""Product-page metadata owned by the standalone web application."""

from __future__ import annotations

from api.config.factory_defaults import api_default

APPLICATION_DESCRIPTION: str = api_default("product.description")

CODEBASE_LINKS: dict[str, str] = api_default("product.links")
