from coyote.db.base import BaseHandler
from flask import flash
from flask import current_app as app


class GroupCoverageHandler(BaseHandler):
    """
    Coverage handler from coyote["coverage"]
    """

    def __init__(self, adapter):
        super().__init__(adapter)
        self.set_collection(self.adapter.groupcov_collection)

    def blacklist_coord(self, gene: str, coord: str, region: str, group: str) -> dict:
        """
        Set exon/probe/region as blacklisted
        """
        data = self.get_collection().find_one({ "gene" : gene, "group" : group, "coord" : coord, "region" : region })
        if data:
            return False
        else:
            self.get_collection().insert_one({ "gene" : gene, "group" : group, "coord" : coord, "region" : region })
        return gene
    
    def blacklist_gene(self, gene: str, group: str) -> dict:
        """
        Set gene as blacklisted
        """
        data = self.get_collection().find_one({ "gene" : gene, "group" : group })
        if data:
            return False
        else:
            self.get_collection().insert_one({ "gene" : gene, "group" : group, "region" : "gene" })
        return gene
    
    def get_regions_per_group(self, group: str) -> dict:
        """
        fetch all blacklisted regions for assay
        """
        data = self.get_collection().find( { "group" : group } )
        return data
    
    def is_region_blacklisted(self, gene: str, region: str, coord: str, assay: str) -> bool:
        """
        return true/false if region is blacklisted for an assay
        """
        data = self.get_collection().find_one({ "gene" : gene, "group" : assay, "coord" : coord, "region" : region })
        if data:
            return True
        else:
            return False
        
    def is_gene_blacklisted(self, gene: str, group: str) -> bool:
        """
        return true/false if gene is blacklisted for assay
        """
        data = self.get_collection().find_one({ "gene" : gene, "group" : group, "region" : "gene" })
        if data:
            return True
        else:
            return False
