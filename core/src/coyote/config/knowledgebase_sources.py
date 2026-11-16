# SPDX-FileCopyrightText: 2026 Ram Nanduri
# SPDX-License-Identifier: GPL-3.0-only

"""Public clinical knowledgebase contracts shared by application workflows."""

from coyote.config.factory_defaults import factory_value

EXTERNAL_KNOWLEDGEBASE_LINKS: dict[str, str] = factory_value("knowledgebases.external_links")

# These are public vendor API contracts, not center deployment settings.
PUBLIC_KNOWLEDGEBASE_API_URLS: dict[str, str] = factory_value("knowledgebases.public_api_urls")


def oncokb_gene_url(symbol: object) -> str:
    """Return the stable public OncoKB gene page for a gene symbol."""
    return f"{EXTERNAL_KNOWLEDGEBASE_LINKS['oncokb_gene']}/{str(symbol or '').strip()}"
