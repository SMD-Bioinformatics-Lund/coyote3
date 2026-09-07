"""Repository-owned product metadata exposed by the public application pages."""

from __future__ import annotations

APPLICATION_DESCRIPTION = "Clinical genomics interpretation, review, and reporting service."

CODEBASE_LINKS: dict[str, str] = {
    "repository_url": "https://github.com/SMD-Bioinformatics-Lund/coyote3",
    "license_url": "https://github.com/SMD-Bioinformatics-Lund/coyote3/blob/master/LICENSE.txt",
    "issues_url": "https://github.com/SMD-Bioinformatics-Lund/coyote3/issues",
    "bug_report_url": "https://github.com/SMD-Bioinformatics-Lund/coyote3/issues/new?template=bug_report.md",
    "feature_request_url": "https://github.com/SMD-Bioinformatics-Lund/coyote3/issues/new?template=feature_request.md",
    "support_request_url": "https://github.com/SMD-Bioinformatics-Lund/coyote3/issues/new?template=support_request.md",
}

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
