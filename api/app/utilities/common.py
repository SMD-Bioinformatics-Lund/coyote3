"""Runtime utility dependencies shared by HTTP and workflow services."""

from __future__ import annotations

from typing import Any

from werkzeug.security import generate_password_hash

from api.app.utilities import serialization
from coyote3.domain.common import assay_filters as domain_assay_filters


class CommonUtility:
    """Provide runtime-bound helpers used by the service container."""

    @staticmethod
    def hash_password(password: str) -> str:
        """Generate a salted password hash using PBKDF2-HMAC-SHA256.

        Args:
            password (str): The plaintext password to hash.

        Returns:
            A password hash containing the algorithm, iteration count, random
            salt, and digest in Werkzeug's storage format.

        Notes:
            Werkzeug selects its default iteration count and generates the salt.
        """
        return generate_password_hash(password, method="pbkdf2:sha256")

    @staticmethod
    def get_assay_genelist_names(genelists: dict) -> list:
        """Extract IDs from an iterable of gene-list documents.

        Args:
            genelists: Documents, normally a list, each containing _id.

        Returns:
            A new list of IDs in input order, preserving duplicates and null IDs.

        Raises:
            KeyError: A document lacks _id.
        """
        return domain_assay_filters.get_assay_genelist_names(genelists)

    @staticmethod
    def convert_to_serializable(data: Any) -> list | dict | str | Any:
        """Recursively convert supported objects to plain containers and scalar text.

        Args:
            data: Value or nested structure, including Pydantic models and objects
                with a callable dict method defined on their type.

        Returns:
            ObjectIds become strings and dates/datetimes become ISO text. Models
            and mappings become dictionaries (including converted keys); lists,
            tuples, and sets become lists. Other values, including None, pass
            through unchanged, so arbitrary inputs are not guaranteed JSON-safe.

        Notes:
            Delegates without changing caller containers; custom dict methods
            are invoked and their errors propagate.
        """
        return serialization.convert_to_serializable(data)

    @staticmethod
    def format_filters_from_form(form_data: Any, assay_config_schema: dict) -> dict:
        """Extract schema-selected values and truthy checkbox groups from a form.

        Args:
            form_data: Dictionary or iterable of fields exposing name and data.
            assay_config_schema: Schema with sections.filters as a mapping or
                list of field names/descriptors; missing sections select nothing.

        Returns:
            A new dictionary of schema fields. Checkbox prefixes vep_, snvlist_,
            fusionlist_, fusioncaller_, fusioneffect_, and cnveffect_ populate
            corresponding lists in submission order, with prefix text removed.
            Other missing fields become None; schema defaults are not applied.
            Inputs are not mutated, but ordinary field values remain shared.
        """
        return domain_assay_filters.format_filters_from_form(form_data, assay_config_schema)

    @staticmethod
    def get_case_and_control_sample_ids(sample_doc: dict) -> dict:
        """Extract truthy case and control identifiers without changing the sample.

        Args:
            sample_doc: Document with optional case_id and control_id values.

        Returns:
            A new dictionary with case/control entries; absent, null, and other
            falsy identifiers are omitted.
        """
        return domain_assay_filters.get_case_and_control_sample_ids(sample_doc)

    @staticmethod
    def get_sample_effective_genes(
        sample: dict,
        asp_doc: dict,
        checked_gl_dict: dict,
        target: str = "snv",
        intent: str = "somatic",
    ) -> tuple:
        """Resolve target-specific gene coverage using the canonical domain helper.

        Args:
            sample: Sample filters, asp_category, and analysis_intents used to
                resolve the profile and ad-hoc genes; absent filters are normalized.
            asp_doc: Panel covered_genes and asp_family settings.
            checked_gl_dict: Records keyed by list IDs selected for this target;
                None means no selected lists. Records are copied before annotation.
            target: Analysis scope, normally snv (default), cnv, fusion, or
                translocation. Other values do not restrict lists by list_type.
            intent: Filter profile to resolve, defaulting to somatic.

        Returns:
            Coverage-annotated records and deduplicated active covered genes as a
            pair. With no applicable lists or ad-hoc genes, uses sorted panel
            eligibility. Empty genes select no findings; caller documents are not mutated.
        """
        return domain_assay_filters.get_sample_effective_genes(
            sample,
            asp_doc,
            checked_gl_dict,
            target=target,
            intent=intent,
        )
