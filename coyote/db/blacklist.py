import pymongo
from bson.objectid import ObjectId
from flask import current_app as app


class BlacklistHandler:
    """
    Blacklist handler from coyote["blacklist"]
    """

    def add_blacklist_data(self, variants, assay):
        short_pos = []

        for var in variants:
            short_pos.append(f"{str(var['CHROM'])}_{str(var['POS'])}_{var['REF']}_{var['ALT']}")

        black_listed = self.blacklist_collection.find({"assay": assay, "pos": {"$in": short_pos}})
        black_dict = {}

        for black_var in black_listed:
            black_dict[black_var["pos"]] = black_var["in_normal_perc"]

        for var in variants:
            pos = f"{str(var['CHROM'])}_{str(var['POS'])}_{var['REF']}_{var['ALT']}"
            if pos in black_dict:
                var["blacklist"] = black_dict[pos]

        return variants[0]
