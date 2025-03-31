from bson.objectid import ObjectId
from coyote.db.base import BaseHandler


class SampleHandler(BaseHandler):
    """
    Sample handler from coyote["samples"]
    """

    def __init__(self, adapter):
        super().__init__(adapter)
        self.set_collection(self.adapter.samples_collection)

    def get_samples(
        self,
        user_groups: list = [],
        report: bool = False,
        search_str: str = "",
        limit=None,
        time_limit=None,
    ):
        query = {"groups": {"$in": user_groups}}
        if report and time_limit:
            query["report_num"] = {"$gt": 0}
            query["reports"] = {"$elemMatch": {"time_created": {"$gt": time_limit}}}
        elif report and not time_limit:
            query["report_num"] = {"$gt": 0}
        else:
            query["$or"] = [{"report_num": {"$exists": False}}, {"report_num": 0}]

        self.app.logger.info(f"this is my search string: {search_str}")
        if len(search_str) > 0:
            query["name"] = {"$regex": search_str}

        print("query", query)
        samples = list(self.get_collection().find(query).sort("time_added", -1))
        if limit:
            samples = samples[:limit]
        return samples

    def get_sample(self, name: str):
        """
        get sample by name
        """
        return self.get_collection().find_one({"name": name})

    def get_sample_with_id(self, id: str):
        """
        get sample by name
        """
        sample = self.get_collection().find_one({"_id": ObjectId(id)})
        return sample

    def get_samples_by_oids(self, sample_oids: list):
        """
        get samples by object ids
        """
        return self.get_collection().find({"_id": {"$in": sample_oids}}, {"name": 1})

    def reset_sample_settings(self, sample_id: str, settings):
        """
        reset sample to default settings
        """
        self.get_collection().update(
            {"name": sample_id},
            {
                "$set": {
                    "filter_max_freq": settings["default_max_freq"],
                    "filter_min_freq": settings["default_min_freq"],
                    "filter_min_depth": settings["default_mindepth"],
                    "filter_min_reads": settings["default_min_reads"],
                    "filter_min_spanreads": settings["default_spanreads"],
                    "filter_min_spanpairs": settings["default_spanpairs"],
                    "checked_csq": settings["default_checked_conseq"],
                    "checked_genelists": settings["default_checked_genelists"],
                    "filter_max_popfreq": settings["default_popfreq"],
                    "checked_fusionlists": settings["default_checked_fusionlists"],
                    "min_cnv_size": settings["default_min_cnv_size"],
                    "max_cnv_size": settings["default_max_cnv_size"],
                    "checked_cnveffects": settings["default_checked_cnveffects"],
                }
            },
        )

    def update_sample_settings(self, sample_str: str, form):
        """
        update sample settings according to form data
        """
        checked_conseq = {}
        checked_genelists = {}
        checked_fusionlists = {}
        checked_fusioneffects = {}
        checked_fusioncallers = {}
        checked_cnveffects = {}
        for fieldname, value in form.data.items():
            if value == True:
                if fieldname.startswith("genelist"):
                    checked_genelists[fieldname] = 1
                elif fieldname.startswith("fusionlist"):
                    checked_fusionlists[fieldname] = 1
                elif fieldname.startswith(
                    "fusioncaller"
                ):  # donot change to fusioncallers, make it singular
                    checked_fusioncallers[fieldname] = 1
                elif fieldname.startswith("fusioneffect"):
                    checked_fusioneffects[fieldname] = 1
                elif fieldname.startswith("cnveffect"):
                    checked_cnveffects[fieldname] = 1
                else:
                    checked_conseq[fieldname] = 1

        self.get_collection().update(
            {"_id": ObjectId(sample_str)},
            {
                "$set": {
                    "filter_max_freq": form.max_freq.data,
                    "filter_min_freq": form.min_freq.data,
                    "filter_min_depth": form.min_depth.data,
                    "filter_min_reads": form.min_reads.data,
                    "filter_min_spanreads": form.min_spanreads.data,
                    "filter_min_spanpairs": form.min_spanpairs.data,
                    "checked_csq": checked_conseq,
                    "checked_genelists": checked_genelists,
                    "filter_max_popfreq": form.max_popfreq.data,
                    "checked_fusionlists": checked_fusionlists,
                    "checked_fusioneffects": checked_fusioneffects,
                    "checked_fusioncallers": checked_fusioncallers,
                    "min_cnv_size": form.min_cnv_size.data,
                    "max_cnv_size": form.max_cnv_size.data,
                    "checked_cnveffects": checked_cnveffects,
                }
            },
        )

    def add_sample_comment(self, sample_id: str, comment_doc: dict) -> None:
        """
        add comment to sample
        """
        self.update_comment(sample_id, comment_doc)

    def hide_sample_comment(self, id: str, comment_id: str) -> None:
        """
        Hide Sample comment
        """
        self.hide_comment(id, comment_id)

    def unhide_sample_comment(self, id: str, comment_id: str) -> None:
        """
        Unhide Sample comment
        """
        self.unhide_comment(id, comment_id)

    def hidden_sample_comments(self, id: str) -> bool:
        """
        Return True if hidden comments for sample else False
        """
        return self.hidden_comments(id)

    def get_all_sample_counts(self, report=None) -> list:
        """
        get all samples
        """
        if report is None:
            samples = self.get_collection().find().sort("time_added", -1).count()
        elif report:
            # samples = [sample for sample in samples if sample.get("report_num", 0) > 0]
            samples = (
                self.get_collection()
                .find({"report_num": {"$gt": 0}})
                .sort("time_added", -1)
                .count()
            )
        elif not report:
            samples = (
                self.get_collection()
                .find(
                    {
                        "$or": [
                            {"report_num": 0},
                            {"report_num": None},
                            {"report_num": {"$exists": False}},
                        ]
                    }
                )
                .sort("time_added", -1)
                .count()
            )

        return samples

    def get_assay_specific_sample_stats(self) -> dict:
        """
        get assay specific stats
        """
        pipeline = [
            {"$unwind": "$groups"},
            {
                "$group": {
                    "_id": "$groups",
                    "total": {"$sum": 1},
                    "report": {"$sum": {"$cond": [{"$gt": ["$report_num", 0]}, 1, 0]}},
                    "pending": {"$sum": {"$cond": [{"$gt": ["$report_num", 0]}, 0, 1]}},
                }
            },
            {
                "$group": {
                    "_id": None,
                    "stats": {
                        "$push": {
                            "group": "$_id",
                            "total": "$total",
                            "report": "$report",
                            "pending": "$pending",
                        }
                    },
                }
            },
            {"$project": {"_id": 0, "stats": 1}},
        ]

        result = list(self.get_collection().aggregate(pipeline))[0].get("stats", [])
        assay_specific_stats = {
            stat.get("group"): {
                "total": stat.get("total", 0),
                "report": stat.get("report", 0),
                "pending": stat.get("pending", 0),
            }
            for stat in result
        }
        return assay_specific_stats

    def get_all_samples(self, limit=None, search_str=""):
        """
        Get all the samples
        """

        query = {}
        if len(search_str) > 0:
            query["name"] = {"$regex": search_str}

        if limit:
            samples = self.get_collection().find(query).sort("time_added", -1).limit(limit)
        else:
            samples = self.get_collection().find(query).sort("time_added", -1)

        return samples

    def delete_sample(self, sample_oid: str) -> None:
        """
        delete sample from db
        """
        self.get_collection().delete_one({"_id": ObjectId(sample_oid)})
