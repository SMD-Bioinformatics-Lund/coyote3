# -*- coding: utf-8 -*-
# This file contains the VEPMetaHandler class for managing VEP metadata.

from coyote.db.base import BaseHandler
from flask import current_app as app


class VEPMetaHandler(BaseHandler):
    """
    Handler for managing VEP metadata stored in the coyote database.

    This class provides methods to retrieve metadata, variant class translations,
    consequence translations, and database information for specific VEP versions.
    """

    def __init__(self, adapter):
        super().__init__(adapter)
        self.set_collection(self.adapter.vep_metadata_collection)

    def _get_metadata(self, vep_version: str):
        """
        Retrieve metadata for a specific VEP version, logging a warning if not found.

        Parameters:
            vep_version (str): The version of VEP to retrieve metadata for.

        Returns:
            dict: The metadata document if found, otherwise an empty dictionary.
        """
        doc = self.get_collection().find_one({"_id": vep_version})
        if not doc:
            app.logger.warning(
                f"VEP version {vep_version} not found in metadata."
            )
        return doc or {}

    def get_variant_class_translations(self, vep_version: str):
        """
        Retrieve the variant class translations for a specific VEP version.

        Returns:
            dict: A dictionary containing the variant class translations if available,
            otherwise an empty dictionary.
        """
        doc = self._get_metadata(vep_version)
        return doc.get("variant_class_translations", {})

    def get_conseq_translations(self, vep_version: str) -> dict:
        """
        Retrieve the consequence translations for a specific VEP version.

        Parameters:
            vep_version (str): The version of VEP to retrieve consequence translations for.

        Returns:
            dict: A dictionary containing the consequence translations if available,
            otherwise an empty dictionary.
        """
        doc = self._get_metadata(vep_version)
        return doc.get("conseq_translations", {})

    def get_db_info(
        self, vep_version: str, genome_build: str = "GRCh38"
    ) -> dict:
        """
        Retrieve the database information for a specific VEP version and genome build.

        Parameters:
            vep_version (str): The version of VEP to retrieve database information for.
            genome_build (str, optional): The genome build to retrieve database information for.
                Defaults to "GRCh38".

        Returns:
            dict: A dictionary containing the database information if available,
            otherwise an empty dictionary.
        """
        doc = self._get_metadata(vep_version)
        db_info = doc.get("db_info", {}).get(genome_build)
        if not db_info:
            app.logger.warning(
                f"Database info for genome build {genome_build} not found in metadata."
            )
            return {}
        return db_info
