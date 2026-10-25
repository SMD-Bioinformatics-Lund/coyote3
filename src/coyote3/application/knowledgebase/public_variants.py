"""On-demand public variant annotations with explicitly injected lookup capabilities."""

from collections.abc import Callable
from typing import Any


class PublicVariantAnnotations:
    """Prepare public knowledgebase queries from owned findings without transport dependencies."""

    def __init__(
        self,
        *,
        oncokb_enabled: bool,
        clinpgx_enabled: bool,
        oncokb_lookup: Callable[[dict[str, Any], dict[str, Any]], dict[str, Any]],
        clinpgx_lookup: Callable[..., dict[str, Any]],
        local_gene_lookup: Callable[[str], dict[str, Any] | None],
    ) -> None:
        """Bind current feature switches, public clients and the local ClinPGx reference reader."""
        self.oncokb_enabled, self.clinpgx_enabled = oncokb_enabled, clinpgx_enabled
        self._oncokb, self._clinpgx, self._local_gene = (
            oncokb_lookup,
            clinpgx_lookup,
            local_gene_lookup,
        )

    def oncokb(self, sample: dict[str, Any], variant: dict[str, Any]) -> dict[str, Any]:
        """Return public OncoKB evidence or the established disabled result.

        Args:
            sample: Sample whose access and finding ownership have been established by the SDK.
            variant: Owned small variant used to prepare the existing public query.

        Returns:
            Existing public lookup result, including its source and query diagnostics.
        """
        if not self.oncokb_enabled:
            return {
                "status": "disabled",
                "message": "Public OncoKB lookups are disabled by application controls.",
                "query": {},
                "responses": {},
                "failures": {},
            }
        return self._oncokb(sample, variant)

    def clinpgx(self, variant: dict[str, Any]) -> dict[str, Any]:
        """Resolve the selected gene's public ClinPGx context using current local accession data.

        Args:
            variant: Owned small variant with its established selected transcript annotation.

        Returns:
            The existing disabled, not-queried or successful gene-knowledge result.
        """
        if not self.clinpgx_enabled:
            return {
                "status": "disabled",
                "message": "Public ClinPGx lookups are disabled by application controls.",
                "query": {},
                "local_record": None,
                "response": None,
            }
        selected = variant.get("INFO", {}).get("selected_CSQ", {}) or {}
        symbol = str(selected.get("SYMBOL") or "").strip()
        local = self._local_gene(symbol)
        accession = str((local or {}).get("pharmgkb_accession_id") or "").strip()
        if not symbol and not accession:
            return {
                "status": "not_queried",
                "message": "No gene symbol is available for this variant.",
                "query": {},
                "local_record": None,
                "response": None,
            }
        response = self._clinpgx(clinpgx_id=accession or None, symbol=symbol or None)
        return {
            "status": "ok",
            "source": "api.clinpgx.org",
            "license": "CC BY-SA 4.0; subject to ClinPGx Data Usage Policy",
            "query": {"clinpgx_id": accession, "symbol": symbol},
            "local_record": local,
            "response": response,
        }
