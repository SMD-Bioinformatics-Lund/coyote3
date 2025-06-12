#  Copyright (c) 2025 Coyote3 Project Authors
#  All rights reserved.
#
#  This source file is part of the Coyote3 codebase.
#  The Coyote3 project provides a framework for genomic data analysis,
#  interpretation, reporting, and clinical diagnostics.
#
#  Unauthorized use, distribution, or modification of this software or its
#  components is strictly prohibited without prior written permission from
#  the copyright holders.
#

"""
CanonicalHandler module for Coyote3
===================================

This module defines the `CanonicalHandler` class used for accessing and managing
canonical transcript data in MongoDB.

It is part of the `coyote.db` package and extends the base handler functionality.

NOTE: This module will be deprecated in the future. Please migrate to other sources.
"""


# -------------------------------------------------------------------------
# Imports
# -------------------------------------------------------------------------
from coyote.db.base import BaseHandler


# -------------------------------------------------------------------------
# Class Definition
# -------------------------------------------------------------------------
class CanonicalHandler(BaseHandler):
    """
    CanonicalHandler class for managing canonical transcript data.

    This class provides methods to interact with canonical transcript data stored in MongoDB,
    including retrieving and formatting canonical transcripts for genes or transcripts.
    """

    def __init__(self, adapter):
        """
        Initialize the handler with a given adapter and bind the collection.
        """
        super().__init__(adapter)
        self.set_collection(self.adapter.canonical_collection)

    def get_canonical_by_genes(self, genes: list) -> dict:
        """
        Retrieve canonical transcripts for multiple genes.

        This method queries the database to find canonical transcripts associated
        with a list of genes and returns the formatted results.

        Args:
            genes (list): A list of gene names for which canonical transcripts are to be retrieved.

        Returns:
            dict: A dictionary where keys are gene names and values are their corresponding canonical transcripts.
        """
        canonical = self.get_collection().find({"gene": {"$in": genes}})
        return self.format_canonical(canonical)

    def get_canonical_by_gene(self, gene: str) -> dict:
        """
        Retrieve the canonical transcript for a specific gene.

        This method queries the database to find the canonical transcript
        associated with the given gene.

        Args:
            gene (str): The name of the gene for which the canonical transcript is to be retrieved.

        Returns:
            dict: A dictionary containing the canonical transcript data for the specified gene.
        """
        canonical = self.get_collection().find_one({"gene": gene})
        return canonical

    def get_canonical_by_transcript(self, transcript: str) -> dict:
        """
        Retrieve the canonical transcript for a specific transcript.

        This method queries the database to find the canonical transcript
        associated with the given transcript.

        Args:
            transcript (str): The name of the transcript for which the canonical transcript is to be retrieved.

        Returns:
            dict: A dictionary containing the canonical transcript data for the specified transcript.
        """
        canonical = self.get_collection().find_one({"canonical": transcript})
        return canonical

    def get_canonical_by_transcripts(self, transcripts: list) -> dict:
        """
        Retrieve canonical transcripts for multiple transcripts.

        This method queries the database to find canonical transcripts associated
        with a list of transcripts and returns the formatted results.

        Args:
            transcripts (list): A list of transcript names for which canonical transcripts are to be retrieved.

        Returns:
            dict: A dictionary where keys are gene names and values are their corresponding canonical transcripts.
        """
        canonical = self.get_collection().find(
            {"canonical": {"$in": transcripts}}
        )
        return self.format_canonical(canonical)

    def format_canonical(self, canonical_data: list[dict]) -> dict:
        """
        Formats canonical transcript data for genes.

        This method processes a list of canonical transcript data dictionaries
        and organizes them into a dictionary where the keys are gene names
        and the values are their corresponding canonical transcripts.

        Args:
            canonical_data (list[dict]): A list of dictionaries containing canonical transcript data.

        Returns:
            dict: A dictionary mapping gene names to their canonical transcripts.
        """
        canonical_dict = {}
        for c in canonical_data:
            canonical_dict[c["gene"]] = c["canonical"]
        return canonical_dict
