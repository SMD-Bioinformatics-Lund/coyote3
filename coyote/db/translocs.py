class TranslocsHandler:
    
    def get_sample_translocations(self, sample_id: str):
        transloc_iter = self.transloc_collection.find( { "SAMPLE_ID" : sample_id } )
        return transloc_iter