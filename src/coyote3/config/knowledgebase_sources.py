"""Public clinical knowledgebase contracts shared by application workflows."""

EXTERNAL_KNOWLEDGEBASE_LINKS: dict[str, str] = {
    "oncokb_gene": "https://www.oncokb.org/gene",
}

# These are public vendor API contracts, not center deployment settings.
PUBLIC_KNOWLEDGEBASE_API_URLS: dict[str, str] = {
    "oncokb": "https://public.api.oncokb.org/api/v1",
    "clinpgx": "https://api.clinpgx.org/v1",
}


def oncokb_gene_url(symbol: object) -> str:
    """Return the stable public OncoKB gene page for a gene symbol."""
    return f"{EXTERNAL_KNOWLEDGEBASE_LINKS['oncokb_gene']}/{str(symbol or '').strip()}"
