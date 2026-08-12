"""Public OncoKB API client.

The public endpoint does not require an OncoKB token and excludes therapeutic
data. Coyote3 uses this client for explicit on-demand detail lookups and the
administrator-triggered public reference refresh; routine dense tables use the
local cache for speed.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable
from typing import Any

import httpx

from api.domain.core.dna.notation import one_letter_p

PUBLIC_ONCOKB_EVIDENCE_TYPES = [
    "GENE_SUMMARY",
    "MUTATION_EFFECT",
    "DIAGNOSTIC_SUMMARY",
    "PROGNOSTIC_SUMMARY",
]


def protein_alteration_from_hgvsp(value: str | None) -> str:
    """Convert selected CSQ HGVSp into OncoKB protein-change notation."""
    if not value:
        return ""
    protein = str(value).split(":")[-1].strip()
    if not protein or protein in {"-", "."}:
        return ""
    alteration = one_letter_p(protein).replace("p.", "").strip()
    return "" if alteration in {"", "-", "."} else alteration


def reference_genome_from_sample(sample: dict[str, Any]) -> str:
    """Map Coyote3 sample genome build values to OncoKB reference genome names."""
    build = str(sample.get("genome_build") or sample.get("reference_genome") or "38").upper()
    return "GRCh37" if "37" in build else "GRCh38"


def _first_alt(value: Any) -> str:
    """Return the first alternate allele from common VCF storage shapes."""
    if isinstance(value, list | tuple):
        return str(value[0] if value else "").strip()
    return str(value or "").split(",")[0].strip()


def _refseq_chromosome_name(accession: str) -> str:
    """Map RefSeq chromosome accessions to OncoKB HGVSg chromosome labels."""
    prefix = accession.split(".", maxsplit=1)[0].upper()
    if prefix.startswith("NC_"):
        number = prefix.removeprefix("NC_")
        if number.isdigit():
            chrom_number = int(number)
            if 1 <= chrom_number <= 22:
                return str(chrom_number)
            if chrom_number == 23:
                return "X"
            if chrom_number == 24:
                return "Y"
    if prefix == "NC_012920":
        return "MT"
    return ""


def normalize_hgvsg_for_oncokb(value: str | None) -> str:
    """Normalize HGVSg into OncoKB's chromosome-label format.

    OncoKB examples use values like `7:g.140453136A>T`. VEP or other tools may
    store equivalent values as `chr7:g...` or `NC_000007.14:g...`; normalize
    those prefixes while preserving the HGVS edit string.
    """
    hgvsg = str(value or "").strip()
    if not hgvsg or hgvsg in {"-", "."} or ":g." not in hgvsg:
        return ""
    chrom, edit = hgvsg.split(":g.", maxsplit=1)
    chrom = chrom.strip()
    if chrom.lower().startswith("chr"):
        chrom = chrom[3:]
    elif chrom.upper().startswith("NC_"):
        chrom = _refseq_chromosome_name(chrom)
    chrom = chrom.upper() if chrom.upper() in {"X", "Y", "MT", "M"} else chrom
    if chrom == "M":
        chrom = "MT"
    return f"{chrom}:g.{edit}" if chrom and edit else ""


def _hgvsg_from_csq(csq: dict[str, Any]) -> str:
    """Extract VEP-provided HGVSg from a selected transcript record."""
    for key in ("HGVSg", "HGVSG", "hgvsg"):
        value = normalize_hgvsg_for_oncokb(csq.get(key))
        if value:
            return value
    return ""


def hgvsg_from_variant(variant: dict[str, Any]) -> str:
    """Return a safe HGVSg query value for OncoKB.

    VEP-provided HGVSg is preferred because it handles indel normalization and
    transcript-independent genomic notation. If no HGVSg is stored, Coyote3 only
    constructs HGVSg for simple SNVs where the notation is unambiguous from VCF
    `CHROM`, `POS`, `REF`, and `ALT`.
    """
    csq = variant.get("INFO", {}).get("selected_CSQ", {}) or {}
    hgvsg = _hgvsg_from_csq(csq)
    if hgvsg:
        return hgvsg

    chrom = str(variant.get("CHROM") or variant.get("chrom") or "").strip()
    pos = variant.get("POS") or variant.get("pos")
    ref = str(variant.get("REF") or variant.get("ref") or "").strip()
    alt = _first_alt(variant.get("ALT") or variant.get("alt"))
    if not chrom or not pos or len(ref) != 1 or len(alt) != 1:
        return ""
    chrom = chrom.removeprefix("chr").removeprefix("CHR")
    if not chrom or alt in {"-", "."} or ref in {"-", "."}:
        return ""
    return normalize_hgvsg_for_oncokb(f"{chrom}:g.{pos}{ref}>{alt}")


class PublicOncoKbClient:
    """Tiny synchronous client for public OncoKB endpoints."""

    def __init__(self, *, base_url: str, timeout: float = 3.0) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    @staticmethod
    def build_protein_change_query(
        *, sample: dict[str, Any], variant: dict[str, Any]
    ) -> dict[str, Any] | None:
        """Build a public OncoKB protein-change query for one small variant."""
        csq = variant.get("INFO", {}).get("selected_CSQ", {}) or {}
        gene = str(csq.get("SYMBOL") or "").strip()
        alteration = protein_alteration_from_hgvsp(csq.get("HGVSp"))
        if not gene or not alteration:
            return None
        return {
            "id": str(variant.get("_id") or ""),
            "gene": {"hugoSymbol": gene},
            "alteration": alteration,
            "referenceGenome": reference_genome_from_sample(sample),
            "evidenceTypes": PUBLIC_ONCOKB_EVIDENCE_TYPES,
        }

    @staticmethod
    def build_hgvsg_query(
        *, sample: dict[str, Any], variant: dict[str, Any]
    ) -> dict[str, Any] | None:
        """Build a public OncoKB HGVSg query for one small variant."""
        hgvsg = hgvsg_from_variant(variant)
        if not hgvsg:
            return None
        return {
            "id": str(variant.get("_id") or ""),
            "hgvsg": hgvsg,
            "referenceGenome": reference_genome_from_sample(sample),
            "evidenceTypes": PUBLIC_ONCOKB_EVIDENCE_TYPES,
        }

    @staticmethod
    def build_annotation_query(
        *, sample: dict[str, Any], variant: dict[str, Any]
    ) -> tuple[str, dict[str, Any]] | None:
        """Build the preferred public OncoKB query for a small variant."""
        hgvsg_query = PublicOncoKbClient.build_hgvsg_query(sample=sample, variant=variant)
        if hgvsg_query is not None:
            return "hgvsg", hgvsg_query
        protein_query = PublicOncoKbClient.build_protein_change_query(
            sample=sample,
            variant=variant,
        )
        if protein_query is not None:
            return "protein_change", protein_query
        return None

    @staticmethod
    def query_hash(query: dict[str, Any]) -> str:
        """Return a stable cache key for a public OncoKB query."""
        if query.get("hgvsg"):
            cache_identity = {
                "queryType": "hgvsg",
                "hgvsg": query.get("hgvsg"),
                "referenceGenome": query.get("referenceGenome"),
                "evidenceTypes": sorted(query.get("evidenceTypes") or []),
            }
        else:
            cache_identity = {
                "queryType": "protein_change",
                "gene": (query.get("gene") or {}).get("hugoSymbol"),
                "alteration": query.get("alteration"),
                "referenceGenome": query.get("referenceGenome"),
                "evidenceTypes": sorted(query.get("evidenceTypes") or []),
            }
        canonical = json.dumps(cache_identity, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    def annotate_variant(
        self, *, sample: dict[str, Any], variant: dict[str, Any]
    ) -> dict[str, Any]:
        """Annotate a small variant through the public OncoKB API."""
        csq = variant.get("INFO", {}).get("selected_CSQ", {}) or {}
        gene = str(csq.get("SYMBOL") or "").strip()
        built_query = self.build_annotation_query(sample=sample, variant=variant)
        if not gene:
            return {
                "status": "not_queried",
                "message": "No gene symbol is available for this variant.",
                "query": {},
                "response": None,
            }
        if built_query is None:
            return {
                "status": "not_queried",
                "message": "No HGVSg or protein alteration is available for public OncoKB lookup.",
                "query": {"gene": gene},
                "response": None,
            }
        query_method, query = built_query
        payload = (
            self.annotate_hgvsgs([query])
            if query_method == "hgvsg"
            else self.annotate_protein_changes([query])
        )
        annotation = payload[0] if payload else None
        return {
            "status": "ok",
            "source": "public.api.oncokb.org",
            "license": "public; therapeutic data excluded",
            "query_method": query_method,
            "query": query,
            "response": annotation,
        }

    def annotate_hgvsgs(self, queries: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
        """Batch annotate public OncoKB HGVSg queries."""
        payload = [dict(query) for query in queries]
        if not payload:
            return []
        with httpx.Client(timeout=self.timeout) as client:
            response = client.post(
                f"{self.base_url}/annotate/mutations/byHGVSg",
                json=payload,
                headers={"Accept": "application/json"},
            )
            response.raise_for_status()
            response_payload = response.json()
        if isinstance(response_payload, list):
            return response_payload
        if isinstance(response_payload, dict):
            return [response_payload]
        return []

    def annotate_protein_changes(self, queries: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
        """Batch annotate public OncoKB protein-change queries."""
        payload = [dict(query) for query in queries]
        if not payload:
            return []
        with httpx.Client(timeout=self.timeout) as client:
            response = client.post(
                f"{self.base_url}/annotate/mutations/byProteinChange",
                json=payload,
                headers={"Accept": "application/json"},
            )
            response.raise_for_status()
            response_payload = response.json()
        if isinstance(response_payload, list):
            return response_payload
        if isinstance(response_payload, dict):
            return [response_payload]
        return []

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
