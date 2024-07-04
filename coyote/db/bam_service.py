from coyote.db.base import BaseHandler


class BamServiceHandler(BaseHandler):
    """
    Bam service handler from BAM_Service["samples"]
    """

    def __init__(self, adapter):
        super().__init__(adapter)
        self.set_collection(self.adapter.bam_samples)

    def get_bams(self, sample_ids):
        """
        Get bam paths for a list of sample ids
        """

        bam_id = {}
        for sample in sample_ids:
            bams = list(self.get_collection().find({"id": str(sample_ids[sample])}))
            for bam in bams:
                if sample_ids[sample] == bam["id"]:
                    if bam["id"] in bam_id:
                        bam_id[bam["id"]].append(bam["bam_path"])
                    else:
                        bam_id[bam["id"]] = [bam["bam_path"]]
                    # bam_id[bam['id']] = bam['bam_path']
        return bam_id
