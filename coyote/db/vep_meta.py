from coyote.db.base import BaseHandler
from flask import current_app as app


class VEPMetaHandler(BaseHandler):
    """
    Variants handler from coyote["variants_idref"]
    """

    def __init__(self, adapter):
        super().__init__(adapter)
        self.set_collection(self.adapter.vep_metadata_collection)

    def get_metadata(self, vep_version):
        """
        Get the metadata for a specific VEP version.
        """
        return self.get_collection().find_one({"_id": vep_version})

    def get_variant_class_translations(self, vep_version):
        """
        Get the variant class translations.
        """
        doc = self.get_collection().find_one({"_id": vep_version})

        if doc is None:
            app.logger.warning(f"VEP version {vep_version} not found in metadata.")
            return {}

        return doc.get("variant_class_translations", {})

    def get_conseq_translations(self, vep_version):
        """
        Get the consequence translations.
        """
        doc = self.get_collection().find_one({"_id": vep_version})
        if doc is None:
            app.logger.warning(f"VEP version {vep_version} not found in metadata.")
            return {}
        return doc.get("conseq_translations", {})

    def get_db_info(self, vep_version, genome_build="GRCh38"):
        """
        Get the database info for a specific VEP version and genome build.
        """
        doc = self.get_collection().find_one({"_id": vep_version})
        if doc is None:
            app.logger.warning(f"VEP version {vep_version} not found in metadata.")
            return {}

        db_info = doc.get("db_info", {}).get(genome_build, None)
        if db_info is None:
            app.logger.warning(
                f"Database info for genome build {genome_build} not found in metadata."
            )
            return {}

        return db_info
