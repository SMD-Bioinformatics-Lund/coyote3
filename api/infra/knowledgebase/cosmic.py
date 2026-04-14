"""
CosmicHandler module for Coyote3
================================

This module defines the `CosmicHandler` class used for accessing and managing
COSMIC (Catalogue Of Somatic Mutations In Cancer) data in MongoDB.

It is part of the `coyote.db` package and extends the base handler functionality.
"""

# -------------------------------------------------------------------------
# Imports
# -------------------------------------------------------------------------
from api.infra.mongo.handlers.base import BaseHandler


# -------------------------------------------------------------------------
# Class Definition
# -------------------------------------------------------------------------
class CosmicHandler(BaseHandler):
    """
    The `CosmicHandler` class is responsible for managing and retrieving data
    from the `cosmic` collection in the MongoDB database. It provides methods
    to fetch cosmic IDs and variants based on specific criteria, such as
    chromosome filters. This class ensures efficient querying and serves as
    an interface between the application and the database for COSMIC data.
    """

    def __init__(self, adapter):
        """
        Initialize the handler with a given adapter and bind the collection.
        """
        super().__init__(adapter)
        self.set_collection(self.adapter.cosmic_collection)

    def ensure_indexes(self) -> None:
        """Create indexes used by chromosome-scoped COSMIC fetch."""
        self.get_collection().create_index(
            [("chr", 1)],
            name="chr_1",
            background=True,
        )

    def get_cosmic_ids(self, chromosomes: list | None = None) -> list:
        """
        Retrieve cosmic IDs for all chromosomes or specific chromosomes.

        This method queries the `cosmic` collection in the database to fetch
        cosmic IDs. If no chromosome list is provided, it retrieves IDs for
        all chromosomes. Otherwise, it filters the results based on the
        provided chromosome list.

        Args:
            chromosomes (list, None): A list of chromosome names to filter by. Defaults to an empty list.

        Returns:
            list: A list of cosmic IDs matching the query criteria.
        """
        query = {} if not chromosomes else {"chr": {"$in": chromosomes}}
        cosmic_ids = self.get_collection().find(query)
        return list(cosmic_ids)
