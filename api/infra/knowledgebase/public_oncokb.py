"""Public OncoKB API client.

The public endpoint does not require an OncoKB token and excludes therapeutic
data. Coyote3 uses this client for explicit on-demand detail lookups and the
administrator-triggered public reference refresh; routine dense tables use the
local cache for speed.
"""

from __future__ import annotations

from typing import Any

import httpx


def reference_genome_from_sample(sample: dict[str, Any]) -> str:
    """Map Coyote3 sample genome build values to OncoKB reference genome names."""
    build = str(sample.get("genome_build") or sample.get("reference_genome") or "38").upper()
    return "GRCh37" if "37" in build else "GRCh38"


def analysis_context_from_sample(sample: dict[str, Any]) -> dict[str, list[str]]:
    """Return supported OncoKB analysis intents recorded for the sample."""
    values = sample.get("analysis_intents") or sample.get("analysis_intent") or []
    if not isinstance(values, list | tuple | set):
        values = [values]
    intents = sorted(
        {
            str(value).strip().lower()
            for value in values
            if str(value).strip().lower() in {"somatic", "germline"}
        }
    )
    if not intents:
        intents = ["somatic"]
    return {"analysis_intents": intents}


def _first_alt(value: Any) -> str:
    """Return the first alternate allele from common VCF storage shapes."""
    if isinstance(value, list | tuple):
        return str(value[0] if value else "").strip()
    return str(value or "").split(",")[0].strip()


def genomic_location_from_variant(variant: dict[str, Any]) -> str:
    """Return OncoKB's exact genomic-location argument from stored VCF fields."""
    chrom = str(variant.get("CHROM") or variant.get("chrom") or "").strip()
    pos = variant.get("POS") or variant.get("pos")
    ref = str(variant.get("REF") or variant.get("ref") or "").strip()
    alt = _first_alt(variant.get("ALT") or variant.get("alt"))
    if not chrom or pos in {None, ""} or not ref or not alt:
        return ""
    try:
        start = int(pos)
    except (TypeError, ValueError):
        return ""
    chrom = chrom.removeprefix("chr").removeprefix("CHR").upper()
    if chrom == "M":
        chrom = "MT"
    if start <= 0 or not chrom or alt in {"-", ".", "*"} or ref in {"-", ".", "*"}:
        return ""
    return f"{chrom},{start},{start + len(ref) - 1},{ref},{alt}"


class PublicOncoKbClient:
    """Tiny synchronous client for public OncoKB endpoints."""

    def __init__(self, *, base_url: str, timeout: float = 3.0) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    def annotate_variant(
        self, *, sample: dict[str, Any], variant: dict[str, Any]
    ) -> dict[str, Any]:
        """Annotate a small variant through the public OncoKB API."""
        analysis_context = analysis_context_from_sample(sample)
        query = {
            "referenceGenome": reference_genome_from_sample(sample),
            "genomicLocation": genomic_location_from_variant(variant),
        }
        if not query["genomicLocation"]:
            return {
                "status": "not_queried",
                "message": "A complete chromosome, position, reference allele, and alternate allele are required for public OncoKB lookup.",
                "query": query,
                "analysis_context": analysis_context,
                "responses": {},
            }
        responses: dict[str, Any] = {}
        failures: dict[str, str] = {}
        for intent in analysis_context["analysis_intents"]:
            try:
                responses[intent] = self.annotate_genomic_change(intent=intent, query=query)
            except httpx.HTTPError as exc:
                failures[intent] = str(exc)
        return {
            "status": "ok" if responses else "unavailable",
            "source": "public.api.oncokb.org",
            "license": "public; therapeutic data excluded",
            "query_method": "genomic_change",
            "query": query,
            "analysis_context": analysis_context,
            "responses": responses,
            "failures": failures,
        }

    def annotate_genomic_change(self, *, intent: str, query: dict[str, str]) -> dict[str, Any]:
        """Fetch one exact genomic mutation annotation for a clinical intent."""
        path = (
            "/annotate/germline/mutations/byGenomicChange"
            if intent == "germline"
            else "/annotate/mutations/byGenomicChange"
        )
        with httpx.Client(timeout=self.timeout) as client:
            response = client.get(
                f"{self.base_url}{path}",
                params=query,
                headers={"Accept": "application/json"},
            )
            response.raise_for_status()
            response_payload = response.json()
        return response_payload if isinstance(response_payload, dict) else {}

    def cancer_gene_list(self) -> list[dict[str, Any]]:
        """Fetch public OncoKB cancer genes for local marker-cache seeding."""
        with httpx.Client(timeout=self.timeout) as client:
            response = client.get(
                f"{self.base_url}/utils/cancerGeneList",
                headers={"Accept": "application/json"},
            )
            response.raise_for_status()
            response_payload = response.json()
        if isinstance(response_payload, list):
            return [item for item in response_payload if isinstance(item, dict)]
        raise ValueError("Public OncoKB cancer-gene response must be a JSON list")

    def all_curated_genes(self, *, include_evidence: bool = True) -> list[dict[str, Any]]:
        """Fetch public OncoKB curated genes for local summary-cache seeding."""
        with httpx.Client(timeout=self.timeout) as client:
            response = client.get(
                f"{self.base_url}/utils/allCuratedGenes",
                params={"includeEvidence": str(include_evidence).lower()},
                headers={"Accept": "application/json"},
            )
            response.raise_for_status()
            response_payload = response.json()
        if isinstance(response_payload, list):
            return [item for item in response_payload if isinstance(item, dict)]
        raise ValueError("Public OncoKB curated-gene response must be a JSON list")
