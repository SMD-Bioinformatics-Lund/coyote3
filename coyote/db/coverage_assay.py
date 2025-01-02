from coyote.db.base import BaseHandler
from flask import flash
from flask import current_app as app


class CoverageAssayHandler(BaseHandler):
    """
    Coverage handler from coyote["coverage"]
    """

    def __init__(self, adapter):
        super().__init__(adapter)
        self.set_collection(self.adapter.coverageassay_collection)

    def blacklist_coord(self, gene: str, coord: str, region: str, assay: str) -> dict:
        """
        Set exon/probe/region as blacklisted
        """
        data = self.get_collection().find_one({ "gene" : gene, "assay" : assay, "coord" : coord, "region" : region })
        if data:
            return False
        else:
            self.get_collection().insert_one({ "gene" : gene, "assay" : assay, "coord" : coord, "region" : region })
        return gene
    
    def blacklist_gene(self, gene: str, assay: str) -> dict:
        """
        Set gene as blacklisted
        """
        data = self.get_collection().find_one({ "gene" : gene, "assay" : assay })
        if data:
            return False
        else:
            self.get_collection().insert_one({ "gene" : gene, "assay" : assay, "region" : "gene" })
        return gene
    
    def get_regions_per_assay(self, assay: str) -> dict:
        """
        fetch all blacklisted regions for assay
        """
        data = self.get_collection().find( { "assay" : assay } )
        return data
    
    def is_region_blacklisted(self, gene: str, region: str, coord: str, assay: str) -> bool:
        """
        return true/false if region is blacklisted for an assay
        """
        data = self.get_collection().find_one({ "gene" : gene, "assay" : assay, "coord" : coord, "region" : region })
        if data:
            return True
        else:
            return False
        
    def is_gene_blacklisted(self, gene: str, assay: str) -> bool:
        """
        return true/false if gene is blacklisted for assay
        """
        data = self.get_collection().find_one({ "gene" : gene, "assay" : assay, "region" : "gene" })
        if data:
            return True
        else:
            return False
