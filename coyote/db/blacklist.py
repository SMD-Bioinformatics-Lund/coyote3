from coyote.db.base import BaseHandler


class BlacklistHandler(BaseHandler):
    """
    Blacklist handler from coyote["blacklist"]
    """

    def __init__(self, adapter):
        super().__init__(adapter)
        self.set_collection(self.adapter.blacklist_collection)

    def add_blacklist_data(self, variants: list, assay: str) -> dict:
        short_pos = []

        for var in variants:
            short_pos.append(f"{str(var['CHROM'])}_{str(var['POS'])}_{var['REF']}_{var['ALT']}")

        black_listed = self.get_collection().find({"assay": assay, "pos": {"$in": short_pos}})
        black_dict = {}

        for black_var in black_listed:
            black_dict[black_var["pos"]] = black_var["in_normal_perc"]

        for var in variants:
            pos = f"{str(var['CHROM'])}_{str(var['POS'])}_{var['REF']}_{var['ALT']}"
            if pos in black_dict:
                var["blacklist"] = black_dict[pos]

        return variants[0]

    def blacklist_variant(self, var: dict, assay: str) -> str:
        """
        Add a variant to the blacklist collection
        """
        short_pos = f"{str(var['CHROM'])}_{str(var['POS'])}_{var['REF']}_{var['ALT']}"

        if self.get_collection().insert_one(
            {"assay": assay, "in_normal_perc": 1, "pos": short_pos}
        ):
            return True
        else:
            return False
