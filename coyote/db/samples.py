import pymongo
from flask import current_app as app

class SampleHandler:
    def get_samples(self,user_groups: list = [], report: bool = False, search_str: str = ""):
        query = { 'groups': { '$in': user_groups } }
        if report:
            query['report_num'] = {'$gt': 0 }
        else:
            query['$or'] = [ { 'report_num': {'$exists': False } }, { 'report_num': 0 } ]

        app.logger.info(f"this is my search string: {search_str}")
        if len(search_str) > 0:
            query['name'] = {'$regex':search_str}
        app.logger.info(query)
        samples = self.samples_collection.find(query).sort( 'time_added', -1 )
        return samples

    def get_num_samples(self, sample_id: str) ->int:
        gt = self.samples_collection.find_one( { 'SAMPLE_ID': sample_id }, {'GT':1} )
        if gt:
            return len(gt.get("GT"))
        else:
            return 0
    def get_sample( self, name: str):
        """
        get sample by name
        """
        sample = self.samples_collection.find_one( { "name": name } )
        return sample
    
    def get_sample_ids(self, sample_id: str):
        a_var = self.samples_collection.find_one( { 'SAMPLE_ID': sample_id }, {'GT':1} )
        ids = {}
        if a_var:
            for gt in a_var["GT"]:
                ids[gt.get('type')] = gt.get('sample')
        return ids