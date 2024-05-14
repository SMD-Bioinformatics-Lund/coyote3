class CNVsHandler:
    
    def get_sample_cnvs(self, sample_id: str, normal: bool = False):
        cnv_iter = self.cnvs_collection.find( { "SAMPLE_ID" : sample_id } )
        return cnv_iter