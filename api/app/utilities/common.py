"""Runtime utility dependencies shared by HTTP and workflow services."""

from __future__ import annotations

from typing import Any

from werkzeug.security import generate_password_hash

from api.app.runtime_state import current_username
from api.app.utilities import assay_filters, serialization
from api.application.interpretation.report_summary import get_tier_classification
from api.domain.common import assay_filters as domain_assay_filters
from api.domain.common.reporting import utc_now
from api.domain.core.annotation_identity import (
    annotation_context_fields,
    annotation_identity_fields,
)


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
    def merge_sample_settings_with_assay_config(sample_doc: dict, assay_config: dict) -> dict:
        """Replace a sample's filters in place with copied settings or defaults.

        Args:
            sample_doc: Sample to mutate. Truthy filters are retained as a deep
                copy; missing, null, or empty filters select assay defaults.
            assay_config: Default filters source. Missing filters means an empty
                dictionary; explicit null filters remain None.

        Returns:
            The same sample dictionary, with filters replaced and
            use_diagnosis_genelist removed. Individual fields are not merged.
        """
        return assay_filters.merge_sample_settings_with_assay_config(sample_doc, assay_config)

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
        return assay_filters.get_case_and_control_sample_ids(sample_doc)

    @staticmethod
    def create_classified_variant_doc(
        variant: str,
        nomenclature: str,
        class_num: int,
        variant_data: dict,
        **kwargs,
    ) -> Any:
        """Build a classification or annotation dictionary without inserting it.

        Args:
            variant: Primary display identity for the finding.
            nomenclature: Identity category, normally p, c, g, cn, f, or t; passed
                to the canonical context and identity helpers without validation here.
            class_num: Classification stored as class only when text is not supplied.
            variant_data: Source for assay_group, subpanel, and nomenclature-specific
                gene, transcript, and alternate identity fields. Missing assay_group
                and subpanel values become None.
            **kwargs: Only text is used. Its presence, even with None or an empty
                value, stores text instead of class; other keywords are ignored.

        Returns:
            A new dictionary with current request author (falling back to "api"),
            timezone-aware UTC creation time, and canonical context/identity fields.
            The input is not mutated and no database write is performed.
        """
        document = {
            "author": current_username(),
            "time_created": utc_now(),
            "variant": variant,
            "nomenclature": nomenclature,
            "assay": variant_data.get("assay_group", None),
            "subpanel": variant_data.get("subpanel", None),
        }

        if "text" in kwargs:
            document["text"] = kwargs["text"]
        else:
            document["class"] = class_num

        document.update(annotation_context_fields(nomenclature=nomenclature, source=variant_data))

        document.update(
            annotation_identity_fields(
                variant=variant,
                nomenclature=nomenclature,
                source=variant_data,
            )
        )

        return document

    @staticmethod
    def get_tier_classification(data: dict) -> int:
        """Return the highest-numbered tier whose value is not None.

        Args:
            data: Variant document with optional tier1 through tier4 values.
                Falsy values such as False, zero, or empty strings still count.

        Returns:
            The last matching tier number (1-4), or zero when all are absent/null.
        """
        return get_tier_classification(data)

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
            sample: Sample filters, omics_layer, and analysis_intents used to
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
            coverage. Empty genes can mean an unrestricted panel or a selection
            without overlap; caller documents are not mutated.
        """
        return domain_assay_filters.get_sample_effective_genes(
            sample,
            asp_doc,
            checked_gl_dict,
            target=target,
            intent=intent,
        )
