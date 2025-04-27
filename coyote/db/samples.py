from bson.objectid import ObjectId
from coyote.db.base import BaseHandler
from datetime import datetime
from flask_login import current_user


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

    def get_sample_name(self, id: str):
        """
        get sample name by id
        """
        sample = self.get_collection().find_one({"_id": ObjectId(id)})
        return sample.get("name") if sample else None

    def get_samples_by_oids(self, sample_oids: list):
        """
        get samples by object ids
        """
        return self.get_collection().find({"_id": {"$in": sample_oids}}, {"name": 1})

    def reset_sample_settings(self, sample_id: str, default_filters: dict):
        """
        reset sample to default settings
        """
        # Remove unnecessary keys from default_filters
        default_filters.pop("use_diagnosis_genelist", None)

        self.get_collection().update(
            {"_id": ObjectId(sample_id)}, {"$set": {"filters": default_filters}}
        )

    def update_sample_settings(self, sample_str: str, form):
        """
        Update sample.filters based on FilterForm data
        """
        form_data = form.data.copy()

        # Remove non-filter fields
        for key in ["csrf_token", "reset", "submit", "use_diagnosis_genelist"]:
            form_data.pop(key, None)

        # Extract Boolean categories
        vep_consequences = []
        genelists = []
        fusionlists = []
        fusioneffects = []
        fusioncallers = []
        cnveffects = []

        keys_to_remove = []

        for field, value in form_data.items():
            if value is True:
                if field.startswith("genelist_"):
                    genelists.append(field.replace("genelist_", ""))
                elif field.startswith("fusionlist_"):
                    fusionlists.append(field.replace("fusionlist_", ""))
                elif field.startswith("fusioncaller_"):
                    fusioncallers.append(field.replace("fusioncaller_", ""))
                elif field.startswith("fusioneffect_"):
                    fusioneffects.append(field.replace("fusioneffect_", ""))
                elif field.startswith("cnveffect_"):
                    cnveffects.append(field.replace("cnveffect_", ""))
                elif field.startswith("vep_"):
                    vep_consequences.append(field.replace("vep_", ""))

                keys_to_remove.append(field)

        # Clean up processed boolean keys
        for k in keys_to_remove:
            form_data.pop(k, None)

        # Drop all remaining fields that are falsy (e.g. False, "", None)
        form_data = {k: v for k, v in form_data.items() if v}

        # Assemble final filters dict
        filters = {
            **form_data,
            "vep_consequences": vep_consequences,
            "genelists": genelists,
            "fusionlists": fusionlists,
            "fusioneffects": fusioneffects,
            "fusion_callers": fusioncallers,
            "cnveffects": cnveffects,
        }

        # Now update the sample doc
        self.get_collection().update_one(
            {"_id": ObjectId(sample_str)},
            {"$set": {"filters": filters}},
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

    def get_all_samples(self, groups=None, limit=None, search_str=""):
        """
        Get all the samples
        """

        query = {}

        if groups:
            query = {"groups": {"$in": groups}}

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
        return self.get_collection().delete_one({"_id": ObjectId(sample_oid)})

    def save_report(self, sample_id: str, report_id: str, filepath: str) -> bool | None:
        """
        save report to sample
        """
        report_num = int(report_id.split(".")[-1])
        return self.get_collection().update(
            {"name": sample_id},
            {
                "$push": {
                    "reports": {
                        "_id": ObjectId(),
                        "report_num": report_num,
                        "report_id": f"{report_id}",
                        "filepath": filepath,
                        "author": current_user.username,
                        "time_created": datetime.now(),
                    }
                },
                "$set": {"report_num": report_num},
            },
        )

    def get_report(self, sample_id: str, report_id: str) -> dict | None:
        """
        Get a specific report from the reports array of a sample document
        """
        doc = self.get_collection().find_one(
            {"name": sample_id, "reports.report_id": report_id}, {"reports": 1}
        )

        if not doc:
            return None

        for report in doc.get("reports", []):
            if report.get("report_id") == report_id:
                return report

        return None
