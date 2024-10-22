from coyote.db.base import BaseHandler


class IARCTP53Handler(BaseHandler):
    """
    IARC TP53 handler from coyote["iarc_tp53"]
    """

    def __init__(self, adapter):
        super().__init__(adapter)
        self.set_collection(self.adapter.iarc_tp53_collection)

    def find_iarc_tp53(self, variant: dict) -> dict | None:
        """
        Find iarc tp53 data
        """
        try:
            if variant["INFO"]["selected_CSQ"]["SYMBOL"] == "TP53":

                hgvsc_parts = variant["INFO"]["selected_CSQ"]["HGVSc"].split(":")
                if len(hgvsc_parts) >= 2:
                    hgvsc = hgvsc_parts[1]
                else:
                    hgvsc = hgvsc_parts[0]
                return self.get_collection().find_one({"var": hgvsc})
            else:
                return None
        except Exception as e:
            self.app.logger.error(f"Error finding iarc tp53 data: {e}")
            return None
