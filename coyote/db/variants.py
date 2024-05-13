import pymongo
from flask import current_app as app

class VariantsHandler:
    """
    Users handler from coyote["users"]
    """

    coyote_users_collection: pymongo.collection.Collection
    
    def get_case_variants(self, query: dict):
        """
        Return variants with according to a constructed varquery
        """
        return self.variants_collection.find( query )


    def get_canonical(self, genes_arr)->dict:
        """
        find canonical transcript for genes
        """
        app.logger.info(f"this is my search string: {genes_arr}")
        canonical_dict = {}
        canonical = self.canonical_collection.find( { 'gene': { '$in': genes_arr } } )
        
        for c in canonical:
            canonical_dict[c["gene"]] = c["canonical"]

        return canonical_dict