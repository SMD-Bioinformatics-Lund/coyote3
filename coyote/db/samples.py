import pymongo


class SampleHandler:
    def get_samples(
            self,assay_name: str = None, sample_id=None
    )->list:
        db_query = {}
        live_samples_iter = self.samples_collection.find(db_query).sort( 'time_added', -1 )
        return list(live_samples_iter)