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
CosmicHandler module for Coyote3
================================

This module defines the `CosmicHandler` class used for accessing and managing
COSMIC (Catalogue Of Somatic Mutations In Cancer) data in MongoDB.

It is part of the `coyote.db` package and extends the base handler functionality.
"""

# -------------------------------------------------------------------------
# Imports
# -------------------------------------------------------------------------
from api.db.base import BaseHandler


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
        query = {} if not chr else {"chr": {"$in": chromosomes or []}}
        cosmic_ids = self.get_collection().find(query)
        return list(cosmic_ids)
