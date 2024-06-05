import pymongo
from bson.objectid import ObjectId
from flask import current_app as app


class BamServiceHandler:
    """
    Bam service handler from BAM_Service["samples"]
    """

    def get_bams(self, sample_ids):
        bam_id = {}
        for sample in sample_ids:
            bams = list(self.bam_samples.find({"id": str(sample_ids[sample])}))
            for bam in bams:
                if sample_ids[sample] == bam["id"]:
                    if bam["id"] in bam_id:
                        bam_id[bam["id"]].append(bam["bam_path"])
                    else:
                        bam_id[bam["id"]] = [bam["bam_path"]]
                    # bam_id[bam['id']] = bam['bam_path']
        return bam_id
