"""
HGNCRepository module for Coyote3
===============================

This module defines the `HGNCRepository` class used for accessing and managing
HGNC gene data in MongoDB.

It is part of the MongoDB infrastructure layer.
"""

# -------------------------------------------------------------------------
# Imports
# -------------------------------------------------------------------------
from api.infra.mongo.repositories.base import BaseRepository


# -------------------------------------------------------------------------
# Class Definition
# -------------------------------------------------------------------------
class HGNCRepository(BaseRepository):
    """
    Handler for managing HGNC gene data stored in the coyote database.

    This class provides methods to interact with HGNC gene information,
    including retrieval, management, and querying of gene metadata.
    It is designed to facilitate efficient access to gene-related data
    for downstream genomic analysis workflows.
    """

    def __init__(self, adapter):
        """
        Initialize the repository with a given adapter and bind the collection.
        """
        super().__init__(adapter)
        self.set_collection(self.adapter.hgnc_collection)

    def ensure_indexes(self) -> None:
        """Create indexes used by HGNC symbol lookups."""
        self.get_collection().create_index(
            [("hgnc_symbol", 1)],
            name="hgnc_symbol_1",
            background=True,
        )
        self.get_collection().create_index(
            [("prev_symbol", 1)],
            name="prev_symbol_1",
            background=True,
        )
        self.get_collection().create_index(
            [("alias_symbol", 1)],
            name="alias_symbol_1",
            background=True,
        )

    def get_metadata_by_hgnc_id(self, hgnc_id: str) -> dict:
        """
        Retrieve metadata for a gene using its HGNC ID.

        Args:
            hgnc_id (str): The HGNC ID of the gene.

        Returns:
            dict: The metadata dictionary for the specified gene.
        """
        normalized = str(hgnc_id or "").strip()
        if not normalized:
            return None
        if not normalized.startswith("HGNC:"):
            normalized = f"HGNC:{normalized}"
        return self.get_collection().find_one(
            {"$or": [{"_id": normalized}, {"hgnc_id": normalized}]}
        )

    def get_metadata_by_symbol(self, symbol: str) -> dict:
        """
        Retrieve metadata for a gene by its symbol.

        Args:
            symbol (str): The symbol of the gene.

        Returns:
            dict: The metadata of the gene.
        """
        return self.get_collection().find_one({"hgnc_symbol": symbol})

    def get_metadata_by_symbol_or_alias(self, symbol: str) -> dict:
        """Return HGNC metadata by approved symbol, previous symbol, or alias symbol."""
        normalized = str(symbol or "").strip()
        if not normalized:
            return None
        return self.get_collection().find_one(
            {
                "$or": [
                    {"hgnc_symbol": normalized},
                    {"prev_symbol": normalized},
                    {"alias_symbol": normalized},
                ]
            }
        )

    def get_metadata_by_symbols(self, symbols: list[str]) -> list[dict]:
        """
        Fetch gene metadata for a list of gene symbols.

        This method retrieves metadata for the provided list of gene symbols.
        If the list is empty, it returns an empty list.

        Args:
            symbols (list[str]): A list of gene symbols to fetch metadata for.

        Returns:
            list[dict]: A list of dictionaries containing gene metadata.
        """
        if not symbols:
            return []
        normalized = sorted({str(symbol).strip() for symbol in symbols if str(symbol).strip()})
        if not normalized:
            return []
        return list(
            self.get_collection().find(
                {
                    "$or": [
                        {"hgnc_symbol": {"$in": normalized}},
                        {"prev_symbol": {"$in": normalized}},
                        {"alias_symbol": {"$in": normalized}},
                    ]
                }
            )
            or []
        )
