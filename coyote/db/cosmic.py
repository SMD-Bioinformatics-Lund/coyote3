from coyote.db.base import BaseHandler
from flask import flash
from flask import current_app as app


class CosmicHandler(BaseHandler):
    """
    Cosmic handler from coyote["cosmic"]
    """

    def __init__(self, adapter):
        super().__init__(adapter)
        self.set_collection(self.adapter.cosmic_collection)

    def get_cosmic_ids(self, chr: list = []) -> list:
        """
        Get cosmic ids for all the chromosomes or a specific chromosome
        """
        if not chr:
            cosmic_ids = self.get_collection().find()
        else:
            cosmic_ids = self.get_collection().find({"chr": {"$in": chr}})

        return list(cosmic_ids) if cosmic_ids else []

    # TODO: OLD FUNCTION, CAN BE REMOVED
    def cosmic_variants_in_regions(self, data):
        new_data = []
        for region in data:
            region["cosmic"] = []
            cosmic_ids = self.get_collection().find(
                {
                    "chr": region["chr"],
                    "start": {"$lte": region["end"]},
                    "end": {"$gte": region["start"]},
                },
                {"id": 1, "cnt": 1},
            )
            for cosmic in cosmic_ids:
                del cosmic["_id"]
                region["cosmic"].append(cosmic)
            new_data.append(region)

        return new_data
