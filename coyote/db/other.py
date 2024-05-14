class OtherHandler:
    
    def get_sample_other(self, sample_id: str, normal: bool = False):
        cnv_iter = self.biomarkers_collection.find( { "SAMPLE_ID" : sample_id } )
        return cnv_iter


