"""
VEPMetaHandler module for managing VEP metadata
===============================================

This module provides the `VEPMetaHandler` class for handling VEP metadata stored
in MongoDB, including translations and database information.

It is part of the `coyote.db` package and extends the base handler functionality.
"""

# -------------------------------------------------------------------------
# Imports
# -------------------------------------------------------------------------
from api.infra.mongo.handlers.base import BaseHandler
from api.runtime_state import app


# -------------------------------------------------------------------------
# Class Definition
# -------------------------------------------------------------------------
class VEPMetaHandler(BaseHandler):
    """
    VEPMetaHandler is a class for managing VEP metadata in the database.

    This class provides methods to retrieve metadata, including variant class
    translations, consequence translations, and database information for
    specific VEP versions and genome builds.
    """

    def __init__(self, adapter):
        """
        Initialize the handler with a given adapter and bind the collection.
        """
        super().__init__(adapter)
        self.set_collection(self.adapter.vep_metadata_collection)

    def ensure_indexes(self) -> None:
        """Create lookup index for strict VEP metadata keying."""
        self.get_collection().create_index(
            [("vep_id", 1)],
            name="vep_id_1",
            unique=True,
            background=True,
            partialFilterExpression={"vep_id": {"$exists": True, "$type": "string"}},
        )

    def _get_metadata(self, vep_version: str):
        """
        Retrieve metadata for a specific VEP version, logging a warning if not found.

        Parameters:
            vep_version (str): The version of VEP to retrieve metadata for.

        Returns:
            dict: The metadata document if found, otherwise an empty dictionary.
        """
        doc = self.get_collection().find_one({"vep_id": str(vep_version)})
        if not doc:
            app.logger.warning("VEP version %s not found in metadata.", vep_version)
        return doc or {}

    def _get_latest_metadata(self):
        """Return the latest VEP metadata document when no version is specified."""
        doc = self.get_collection().find_one(sort=[("vep_id", -1)])
        if not doc:
            app.logger.warning("No VEP metadata found in database.")
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

    def get_consequence_group_map(self, vep_version: str | None = None) -> dict[str, list[str]]:
        """Return grouped consequence terms keyed by UI filter group."""
        doc = (
            self._get_metadata(vep_version)
            if vep_version is not None
            else self._get_latest_metadata()
        )
        group_map = doc.get("consequence_groups", {})
        if group_map:
            return {
                str(group).strip(): [str(term).strip() for term in terms if str(term).strip()]
                for group, terms in group_map.items()
                if str(group).strip()
            }

        derived: dict[str, list[str]] = {}
        for consequence, meta in (doc.get("conseq_translations", {}) or {}).items():
            if not isinstance(meta, dict):
                continue
            group = str(meta.get("group") or "").strip()
            term = str(consequence or "").strip()
            if not group or not term:
                continue
            derived.setdefault(group, [])
            if term not in derived[group]:
                derived[group].append(term)
        return derived

    def get_consequence_group_options(self, vep_version: str | None = None) -> list[str]:
        """Return available grouped consequence filter keys."""
        return list(self.get_consequence_group_map(vep_version).keys())

    def get_db_info(self, vep_version: str, genome_build: str = "GRCh38") -> dict:
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
                "Database info for genome build %s not found in metadata.", genome_build
            )
            return {}
        return db_info
