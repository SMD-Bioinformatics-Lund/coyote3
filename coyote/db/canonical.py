from coyote.db.base import BaseHandler


class CanonicalHandler(BaseHandler):

    def __init__(self, adapter):
        super().__init__(adapter)
        self.set_collection(self.adapter.canonical_collection)

    def get_canonical_by_genes(self, genes: list) -> dict:
        """
        find canonical transcript for genes
        """
        self.app.logger.info(f"this is my search string: {genes}")
        canonical = self.get_collection().find({"gene": {"$in": genes}})
        return self.format_canonical(canonical)

    def get_canonical_by_gene(self, gene: str) -> dict:
        """
        find canonical transcript for gene
        """
        canonical = self.get_collection().find_one({"gene": gene})
        return canonical

    def get_canonical_by_transcript(self, transcript: str) -> dict:
        """
        find canonical transcript for gene
        """
        canonical = self.get_collection().find_one({"canonical": transcript})
        return canonical

    def get_canonical_by_transcripts(self, transcripts: list) -> dict:
        """
        find canonical transcript for gene
        """
        canonical = self.get_collection().find({"canonical": {"$in": transcripts}})
        return self.format_canonical(canonical)

    def format_canonical(self, canonical_data: list[dict]) -> dict:
        """
        format canonical transcript for gene
        """
        canonical_dict = {}
        for c in canonical_data:
            canonical_dict[c["gene"]] = c["canonical"]
        return canonical_dict
