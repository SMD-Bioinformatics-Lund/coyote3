"""
BRCARepository module for Coyote3
==============================

This module defines the `BRCARepository` class used for accessing and managing
BRCA data in MongoDB.
It is part of the MongoDB infrastructure layer.
"""

# -------------------------------------------------------------------------
# Imports
# -------------------------------------------------------------------------
from api.infra.mongo.repositories.base import BaseRepository


# -------------------------------------------------------------------------
# Class Definition
# -------------------------------------------------------------------------
class BRCARepository(BaseRepository):
    """
    The `BRCARepository` class provides functionality for accessing and managing
    BRCA-related data stored in the `brcaexchange` collection of MongoDB.

    This class extends the `BaseRepository` and includes methods for querying
    BRCA variant data based on specific assay types.
    """

    def __init__(self, adapter):
        """
        Initialize the repository with a given adapter and bind the collection.
        """
        super().__init__(adapter)
        self.set_collection(self.adapter.brcaexchange_collection)

    COORDINATE_INDEXES = (
        (
            (("chr", 1), ("pos", 1), ("ref", 1), ("alt", 1)),
            {"name": "chr_pos_ref_alt"},
        ),
        (
            (("chr38", 1), ("pos38", 1), ("ref38", 1), ("alt38", 1)),
            {"name": "chr38_pos38_ref38_alt38", "sparse": True},
        ),
    )

    def ensure_indexes(self) -> None:
        """Create indexes used by BRCA exchange coordinate lookups."""
        col = self.get_collection()
        for keys, options in self.COORDINATE_INDEXES:
            col.create_index(list(keys), background=True, **options)

    def get_brca_data(self, variant: dict, genome_build: int | None) -> dict | None:
        """Look up exact variant coordinates in the explicitly selected assembly.

        Args:
            variant: CHROM, POS, REF and ALT from the variant record.
            genome_build: 37 or 38. Missing or unsupported builds do not query the database.

        Returns:
            Matching reference document, or None when no match or valid build exists.
        """
        if genome_build not in (37, 38):
            return None
        suffix = "38" if genome_build == 38 else ""
        return self.get_collection().find_one(
            {
                f"chr{suffix}": str(variant["CHROM"]).removeprefix("chr"),
                f"pos{suffix}": int(variant["POS"]),
                f"ref{suffix}": variant["REF"],
                f"alt{suffix}": variant["ALT"],
            }
        )
