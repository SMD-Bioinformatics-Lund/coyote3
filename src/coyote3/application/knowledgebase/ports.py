"""Network-independent interfaces for external reference catalogues."""

from typing import Any, Protocol


class PublicOncoKbReader(Protocol):
    """Read the public cancer-gene and curated-gene catalogues."""

    def cancer_gene_list(self) -> list[dict[str, Any]]:
        """Return the complete public cancer-gene catalogue."""
        ...

    def all_curated_genes(self, *, include_evidence: bool = True) -> list[dict[str, Any]]:
        """Return curated genes, optionally including public evidence annotations."""
        ...
