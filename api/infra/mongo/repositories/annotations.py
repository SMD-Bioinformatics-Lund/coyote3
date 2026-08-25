"""
AnnotationsRepository module for Coyote3
=====================================

This module defines the `AnnotationsRepository` class used for accessing and managing
annotation data in MongoDB.

It is part of the MongoDB infrastructure layer.
"""

from collections import defaultdict
from copy import deepcopy
from typing import Any, Dict, List, Optional
from urllib.parse import unquote

from bson import ObjectId

from api.contracts.operations import OperationResult
from api.contracts.schemas.registry import normalize_collection_document
from api.domain.core.annotation_identity import (
    ANNOTATION_IDENTITY_FIELDS,
    annotation_context_fields,
    enrich_annotation_identity,
)
from api.domain.core.dna.variant_identity import build_simple_id
from api.infra.mongo.repositories.base import BaseRepository
from api.infra.mongo.repository_utils import utc_now
from api.infra.request_context import current_username


def _annotation_object_id(oid: object) -> ObjectId | None:
    """Return the canonical MongoDB identifier for an annotation."""
    if isinstance(oid, ObjectId):
        return oid
    text = str(oid or "").strip()
    return ObjectId(text) if ObjectId.is_valid(text) else None


def _annotation_class_value(value: Any) -> int | None:
    """Return a contract-valid annotation class."""
    return value if isinstance(value, int) and not isinstance(value, bool) else None


def _annotation_search_query(
    *,
    search_str: str,
    search_mode: str,
    include_annotation_text: bool,
    asp_ids: list | None = None,
) -> dict[str, Any] | None:
    """Build the annotation search query used by tiered-variant search."""
    if not search_str:
        return None

    regex = {"$regex": search_str, "$options": "i"}
    mode = str(search_mode or "variant").lower()
    variant_fields = (
        "variant",
        "hgvsp",
        "hgvsc",
        "genomic",
        "genomic_hash",
    )

    if mode == "gene":
        query: dict[str, Any] = {
            "$or": [
                {"gene": regex},
                {"gene1": regex},
                {"gene2": regex},
            ]
        }
    elif mode == "transcript":
        query = {"$or": [{"transcript": regex}]}
    elif mode == "hgvsp":
        query = {"$or": [{"hgvsp": regex}]}
    elif mode == "hgvsc":
        query = {"$or": [{"hgvsc": regex}]}
    elif mode == "genomic":
        query = {"$or": [{"genomic": regex}, {"genomic_hash": regex}]}
    elif mode == "nomenclature":
        query = {"nomenclature": regex}
    elif mode == "variant":
        query = {"$or": [{field: regex} for field in variant_fields]}
    elif mode == "author":
        query = {"author": regex}
    elif mode == "subpanel":
        query = {"subpanel": regex}
    elif mode == "annotation":
        query = {"text": regex}
    elif mode == "all":
        query = {
            "$or": [
                {"gene": regex},
                {"transcript": regex},
                {"author": regex},
                {"subpanel": regex},
                {"text": regex},
                {"gene1": regex},
                {"gene2": regex},
                *[{field: regex} for field in variant_fields],
            ]
        }
    else:
        return None

    query_parts = [query]
    if not include_annotation_text and mode != "annotation":
        query_parts.append({"$or": [{"text": {"$exists": False}}, {"text": None}, {"text": ""}]})

    if asp_ids:
        query_parts.append({"assay": {"$in": asp_ids}})

    if len(query_parts) == 1:
        return query_parts[0]
    return {"$and": query_parts}


def _text_values(value: Any) -> list[str]:
    """Return unique non-empty identity values without guessing aliases."""
    values = value if isinstance(value, (list, tuple, set)) else [value]
    return list(
        dict.fromkeys(
            normalized for item in values if (normalized := unquote(str(item or "")).strip())
        )
    )


def _small_variant_identity_clauses(
    *, hgvsp: Any, hgvsc: Any, genomic: Any
) -> list[dict[str, Any]]:
    """Build exact matches against the canonical flat annotation identities."""
    clauses: list[dict[str, Any]] = []
    protein_values = _text_values(hgvsp)
    coding_values = _text_values(hgvsc)
    genomic_values = _text_values(genomic)
    if protein_values:
        clauses.append({"hgvsp": {"$in": protein_values}})
    if coding_values:
        clauses.append({"hgvsc": {"$in": coding_values}})
    if genomic_values:
        clauses.append({"genomic": {"$in": genomic_values}})
    return clauses


def _classification_text_lookup_query(annotation: dict[str, Any]) -> dict[str, Any] | None:
    """Build a lookup query for the free-text row matching a class annotation."""
    variant = annotation.get("variant")
    nomenclature = annotation.get("nomenclature")
    if not variant or not nomenclature:
        return None

    query: dict[str, Any] = {
        "variant": variant,
        "nomenclature": nomenclature,
        "text": {"$exists": True, "$type": "string", "$ne": ""},
    }

    for key in ("gene", "gene1", "gene2", "transcript", "assay", "subpanel"):
        if annotation.get(key) is not None:
            query[key] = annotation.get(key)

    return query


# -------------------------------------------------------------------------
# Class Definition
# -------------------------------------------------------------------------
class AnnotationsRepository(BaseRepository):
    """
    AnnotationsRepository is a class responsible for managing annotation data
    stored in the `coyote["annotations"]` MongoDB collection. It provides
    methods to retrieve, insert, update, and delete annotations, as well as
    to handle classifications and comments related to genetic variants.

    This class serves as a key component for efficiently managing and
    querying annotation-related data in the database.
    """

    def __init__(self, adapter):
        """
        Initialize the repository with a given adapter and bind the collection.
        """
        super().__init__(adapter)
        self.set_collection(self.adapter.annotations_collection)

    def ensure_indexes(self) -> None:
        """Ensure indexes.

        Returns:
            None.
        """
        col = self.get_collection()
        col.create_index(
            [("annotation_id", 1)],
            name="annotation_id_1",
            unique=True,
            background=True,
            partialFilterExpression={"annotation_id": {"$exists": True, "$type": "string"}},
        )
        col.create_index([("gene", 1)], name="gene_1", background=True)
        col.create_index([("variant", 1)], name="variant_1", background=True)
        for identity_field in ANNOTATION_IDENTITY_FIELDS:
            col.create_index(
                [(identity_field, 1)],
                name=f"{identity_field}_1",
                background=True,
                sparse=True,
            )
        col.create_index(
            [("variant", 1), ("time_created", 1)],
            name="variant_time_created_1",
            background=True,
        )
        col.create_index(
            [("gene", 1), ("nomenclature", 1), ("variant", 1), ("time_created", 1)],
            name="gene_nomenclature_variant_time_created",
            background=True,
        )
        col.create_index(
            [("nomenclature", 1), ("variant", 1), ("time_created", 1)],
            name="nomenclature_variant_time_created",
            background=True,
        )

    def get_annotation_by_oid(self, oid: str) -> dict | None:
        """
        Retrieve an annotation by its ObjectId.

        This method fetches a single annotation document from the MongoDB
        collection using the provided ObjectId.

        Args:
            oid (str): The ObjectId of the annotation to be retrieved.
        Returns:
            dict | None: The annotation document if found, otherwise None.
        """
        object_id = _annotation_object_id(oid)
        if object_id is None:
            return None
        return self.get_collection().find_one({"_id": object_id})

    def get_annotation_text_by_oid(self, oid: str) -> str | None:
        """
        Retrieve the text of an annotation by its ObjectId.

        This method fetches the 'text' field of a single annotation document
        from the MongoDB collection using the provided ObjectId.

        Args:
            oid (str): The ObjectId of the annotation to be retrieved.

        Returns:
            str | None: The text of the annotation if found, otherwise None.
        """
        object_id = _annotation_object_id(oid)
        if object_id is None:
            return None
        annotation = self.get_collection().find_one({"_id": object_id}, {"text": 1})
        if annotation:
            return annotation.get("text", None)
        return None

    def get_matching_annotation_text(self, annotation: dict[str, Any]) -> str | None:
        """Return the newest free-text annotation matching a class annotation identity."""
        query = _classification_text_lookup_query(annotation)
        if query is None:
            return None
        text_doc = self.get_collection().find_one(query, {"text": 1}, sort=[("time_created", -1)])
        if not text_doc:
            return None
        return text_doc.get("text")

    def get_annotations_by_oids(self, oids: list[object]) -> list[dict]:
        """Return annotation documents for the requested object ids."""
        unique_oids = list(
            dict.fromkeys(
                object_id for oid in oids if (object_id := _annotation_object_id(oid)) is not None
            )
        )
        if not unique_oids:
            return []
        return list(self.get_collection().find({"_id": {"$in": unique_oids}}) or [])

    def insert_annotation_bulk(self, annotations: list) -> Any:
        """
        Insert multiple annotations into the database in bulk.

        This method takes a list of annotation dictionaries and inserts them
        into the MongoDB collection. It is designed for efficiency when
        handling multiple annotations at once.

        Args:
            annotations (list): A list of dictionaries, each representing an
                                annotation to be inserted.

        Returns:
            Any: The result of the insert operation, which may include the
                 inserted document IDs or other relevant information.
        """
        if not annotations:
            return None

        # Create a deep copy to avoid modifying the original list
        annotations_copy = [
            normalize_collection_document("annotation", enrich_annotation_identity(annotation))
            for annotation in deepcopy(annotations)
        ]
        return OperationResult.from_insert_many(
            self.get_collection().insert_many(annotations_copy),
            requested_count=len(annotations_copy),
        )

    def get_global_annotations(self, variant: dict, assay_group: str, subpanel: str) -> tuple:
        """
        Retrieve global annotations for a given variant, assay, and subpanel.

        This method queries the MongoDB collection for annotations that match
        the provided variant's genomic location, gene symbol, and nomenclature
        (HGVSp, HGVSc, or genomic). It prioritizes annotations based on the
        presence of HGVSp, HGVSc, or genomic location in that order.

        Args:
            variant (dict): A dictionary containing variant details, including
                            'CHROM', 'POS', 'REF', 'ALT', and 'INFO' with
                            'selected_CSQ' data.
            assay_group (str): The type of assay being used (e.g., 'solid').
            subpanel (str): The subpanel identifier for further filtering when
                            assay is 'solid'.

        Returns:
            tuple: A tuple containing:
                - annotations_arr (list): A list of all annotations.
                - latest_classification (dict): The latest classification for
                  the current assay.
                - latest_other_arr (list): A list of classifications for other
                  assays and subpanels.
                - annotations_interesting (dict): A dictionary of annotations
                  deemed interesting based on assay and subpanel.
        """
        genomic = ""
        if all(key in variant for key in ("CHROM", "POS", "REF", "ALT")):
            genomic = build_simple_id(
                variant["CHROM"], variant["POS"], variant["REF"], variant["ALT"]
            )
        selected_CSQ = variant.get("INFO", {}).get("selected_CSQ", {})
        hgvsp = unquote(str(selected_CSQ.get("HGVSp") or ""))
        hgvsc = unquote(str(selected_CSQ.get("HGVSc") or ""))
        identity_clauses = _small_variant_identity_clauses(
            hgvsp=hgvsp,
            hgvsc=hgvsc,
            genomic=genomic,
        )

        if selected_CSQ.get("SYMBOL") and identity_clauses:
            annotations = (
                self.get_collection()
                .find({"gene": selected_CSQ["SYMBOL"], "$or": identity_clauses})
                .sort("time_created", 1)
            )
        elif "breakpoint1" in variant and "breakpoint2" in variant:
            fusion_query: dict[str, Any] = {
                "nomenclature": "f",
                "variant": f"{variant['breakpoint1']}^{variant['breakpoint2']}",
            }
            fusion_query.update(annotation_context_fields(nomenclature="f", source=variant))
            annotations = self.get_collection().find(fusion_query).sort("time_created", 1)
        else:
            annotations = []

        latest_classification = {"class": 999}
        latest_classification_other = {}
        annotations_arr = []
        annotations_interesting = {}

        for anno in annotations:
            ## collect latest for current assay (if latest not assigned pick that)
            ## also collect latest anno for all other assigned assays (including non-assays)
            ## special rule for assays with subpanels, solid, tumwgs maybe lymph?
            anno_class = _annotation_class_value(anno.get("class"))
            if anno_class is not None:
                anno["class"] = anno_class
                assay = anno["assay"]
                sub = anno["subpanel"]
                ass_sub = f"{assay}:{sub}"
                if assay_group == "solid":
                    if assay == assay_group and sub == subpanel:
                        latest_classification = anno
                    else:
                        latest_classification_other[ass_sub] = anno["class"]
                elif assay == assay_group:
                    latest_classification = anno
                else:
                    latest_classification_other[ass_sub] = anno["class"]
            if "text" in anno:
                assay = anno["assay"]
                sub = anno["subpanel"]
                ass_sub = f"{assay}:{sub}"
                if assay_group == "solid" and assay == assay_group and sub == subpanel:
                    annotations_interesting[ass_sub] = anno
                elif assay == assay_group:
                    annotations_interesting[assay] = anno
                annotations_arr.append(anno)

        latest_other_arr = []
        for latest_assay in latest_classification_other:
            assay_sub = latest_assay.split(":")
            latest_other_arr.append(
                {
                    "assay": assay_sub[0],
                    "class": latest_classification_other[latest_assay],
                    "subpanel": assay_sub[1] if len(assay_sub) > 1 else None,
                }
            )

        return (
            annotations_arr,
            latest_classification,
            latest_other_arr,
            annotations_interesting,
        )

    def get_additional_classifications(
        self, variant: dict, assay_group: str, subpanel: str
    ) -> list:
        """
        Retrieve additional classifications for a given variant based on specified assay and subpanel.
        This method constructs a query to search for classifications in the database that match the
        provided variant's genes, transcripts, and nomenclature variants (HGVSp and HGVSc). If the
        assay type is 'solid', it further filters the results by assay and subpanel.
        Args:
            variant (dict): A dictionary containing variant details including 'transcripts', 'HGVSp',
                            'HGVSc', and 'genes'.
            assay_group (str): The type of assay being used (e.g., 'solid').
            subpanel (str): The subpanel identifier for further filtering when assay is 'solid'.
        Returns:
            list: A list of annotations that match the query criteria, sorted by the time they were created.

        """
        genomic = variant.get("simple_id", "")
        hgvsp = variant.get("HGVSp", "")
        hgvsc = variant.get("HGVSc", "")
        genes = _text_values(variant.get("genes", []))
        breakpoint1 = variant.get("breakpoint1", "")
        breakpoint2 = variant.get("breakpoint2", "")

        if genomic:
            identity_clauses = _small_variant_identity_clauses(
                hgvsp=hgvsp,
                hgvsc=hgvsc,
                genomic=genomic,
            )
            query = {
                "gene": {"$in": genes},
                "$or": identity_clauses,
                "assay": assay_group,
                "class": {"$exists": True},
            }
        else:
            query = {
                "nomenclature": "f",
                "variant": f"{breakpoint1}^{breakpoint2}",
                "assay": assay_group,
                "class": {"$exists": True},
            }
            query.update(annotation_context_fields(nomenclature="f", source=variant))
        if assay_group == "solid":
            query["subpanel"] = subpanel

        return list(self.get_collection().find(query).sort("time_created", -1).limit(1))

    def insert_classified_variant(
        self,
        variant: str,
        nomenclature: str,
        class_num: int,
        variant_data: dict,
        **kwargs,
    ) -> Any:
        """
        Insert a classified variant into the database.

        This method creates a document representing a classified variant and inserts it into the MongoDB collection.
        The document includes details such as the variant, nomenclature, classification, assay, subpanel, and additional
        metadata like the author and creation time.

        Args:
            variant (str): The variant identifier (e.g., genomic location or variant ID).
            nomenclature (str): The nomenclature type ('p', 'c', 'g', or 'f').
            class_num (int): The classification number assigned to the variant.
            variant_data (dict): A dictionary containing additional variant details, such as:
                - assay (str): The assay type (e.g., 'solid').
                - subpanel (str): The subpanel identifier.
                - gene (str): The gene symbol (if applicable).
                - transcript (str): The transcript identifier (if applicable).
                - gene1 (str): The first gene symbol (if nomenclature is 'f').
                - gene2 (str): The second gene symbol (if nomenclature is 'f').
            **kwargs: Additional optional arguments, such as:
                - text (str): A textual comment or description for the variant.

        Returns:
            Any: The result of the insert operation, which may include the inserted document ID or other relevant information.
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

        document = enrich_annotation_identity(document, source=variant_data)
        document = normalize_collection_document("annotation", document)
        return OperationResult.from_insert_one(self.get_collection().insert_one(document))

    def delete_classified_variant(
        self,
        variant: str,
        nomenclature: str,
        variant_data: dict,
        class_num: int | None = None,
        annotation_text: str | None = None,
    ) -> OperationResult:
        """
        Delete a classified variant from the database.

        This method removes a classified variant document from the MongoDB collection
        based on the provided variant details, nomenclature, and assay information.
        Deletion is limited to the exact assay, subpanel, nomenclature, and
        finding context supplied by the current workflow.

        Args:
            variant (str): The variant identifier (e.g., genomic location or variant ID).
            nomenclature (str): The nomenclature type ('p', 'c', 'g', or 'f').
            variant_data (dict): A dictionary containing additional variant details, such as:
                - assay (str): The assay type (e.g., 'solid').
                - subpanel (str): The subpanel identifier.
                - gene (str): The gene symbol (if applicable).

        Returns:
            A structured write result for the scoped deletion.
        """
        query = {
            "variant": variant,
            "assay": variant_data.get("assay_group", None),
            "nomenclature": nomenclature,
            "subpanel": variant_data.get("subpanel", None),
            **annotation_context_fields(nomenclature=nomenclature, source=variant_data),
        }

        class_filter: dict = {"class": {"$exists": True}}
        if class_num is not None:
            class_filter["class"] = class_num

        delete_clause: list[dict] = [class_filter]
        if annotation_text:
            delete_clause.append({"text": annotation_text})

        scoped_query = {**query, "$or": delete_clause}
        return OperationResult.from_delete(self.get_collection().delete_many(scoped_query))

    def get_gene_annotations(self, gene_name: str) -> list:
        """
        Get all annotations for a given gene.

        This method retrieves all annotations from the MongoDB collection
        that are associated with the specified gene name. The results are
        sorted by the time they were created in ascending order.

        Args:
            gene_name (str): The name of the gene for which annotations
                             are to be retrieved.

        Returns:
            list: A list of annotations related to the specified gene,
                  sorted by creation time.
        """
        return self.get_collection().find({"gene": gene_name}).sort("time_created", 1)

    def add_anno_comment(self, comment: dict) -> Any:
        """
        Add a comment to a variant.

        This method allows adding a comment to a specific variant in the database.
        The comment is expected to be a dictionary containing relevant details
        about the comment, such as the author, timestamp, and the content of the comment.

        Args:
            comment (dict): A dictionary containing the comment details.

        Returns:
            Any: The result of the insert operation
        """
        self.add_comment(
            normalize_collection_document("annotation", enrich_annotation_identity(comment))
        )

    def get_assay_classified_stats(self) -> tuple:
        """
        Retrieve classified statistics for all assays.

        This method constructs an aggregation pipeline to calculate statistics
        for classified variants in the database. It groups the data by assay,
        nomenclature, and classification, and provides counts for each group.

        Returns:
            tuple: A list of dictionaries containing:
                - assay (str): The assay type.
                - nomenclature (str): The nomenclature type ('p', 'c', 'g', etc.).
                - class (int): The classification number.
                - count (int): The count of classified variants for the group.
        """
        assay_class_stats_pipeline = [
            # Match documents where the "class" field exists
            {"$match": {"class": {"$exists": True}}},
            # Sort by variant and time_created to ensure the latest document is first
            {"$sort": {"variant": 1, "time_created": -1}},
            # Group by variant to pick the latest document for each variant
            {
                "$group": {
                    "_id": "$variant",
                    "assay": {"$first": "$assay"},
                    "nomenclature": {"$first": "$nomenclature"},
                    "class": {"$first": "$class"},
                }
            },
            # Group by assay, nomenclature, and class to get counts
            {
                "$group": {
                    "_id": {
                        "assay": "$assay",
                        "nomenclature": "$nomenclature",
                        "class": "$class",
                    },
                    "count": {"$sum": 1},
                }
            },
            # Sort the results by assay, nomenclature, and class for consistency
            {"$sort": {"_id.assay": 1, "_id.nomenclature": 1, "_id.class": 1}},
        ]
        return tuple(self.get_collection().aggregate(assay_class_stats_pipeline))

    def get_classified_stats(self) -> tuple:
        """
        Retrieve statistics for all classified variants.

        This method constructs an aggregation pipeline to calculate statistics
        for classified variants in the database. It groups the data by nomenclature
        and classification, and provides counts for each group.

        Returns:
            list: A list of dictionaries containing:
                - nomenclature (str): The nomenclature type ('p', 'c', 'g', etc.).
                - class (int): The classification number.
                - count (int): The count of classified variants for the group.
        """
        class_stats_pipeline = [
            # Match documents where the "class" field exists
            {"$match": {"class": {"$exists": True}}},
            # Sort by nomenclature, variant, and time_created to ensure the latest document is first
            {"$sort": {"nomenclature": 1, "variant": 1, "time_created": -1}},
            # Group by variant to pick the latest document for each variant
            {
                "$group": {
                    "_id": "$variant",
                    "nomenclature": {"$first": "$nomenclature"},
                    "class": {"$first": "$class"},
                }
            },
            # Group by nomenclature and class to get counts
            {
                "$group": {
                    "_id": {
                        "nomenclature": "$nomenclature",
                        "class": "$class",
                    },
                    "count": {"$sum": 1},
                }
            },
            # Sort the results by nomenclature and class for consistency
            {"$sort": {"_id.nomenclature": 1, "_id.class": 1}},
        ]
        return tuple(self.get_collection().aggregate(class_stats_pipeline))

    def find_variants_by_search_string(
        self,
        search_str: str,
        search_mode: str,
        include_annotation_text: bool,
        asp_ids: list | None = None,
        limit: int | None = None,
    ) -> list:
        """
        Find variants matching the search string.

        This method searches for variants in the database that match the provided
        search string. It looks for matches in the 'variant', 'gene', and 'transcript'
        fields using case-insensitive regular expressions.

        Args:
            search_str (str): The search string to match against variant fields.
            limit (int | None): Optional limit on the number of results to return.
            search_mode (str): The mode of search, can be 'gene', 'transcript', 'variant', 'author', or 'subpanel'.
            include_annotation_text (bool): Whether to include annotations with text.
            asp_ids (list | None): Optional ASP identifiers to filter the results.

        Returns:
            list: A list of variant documents that match the search criteria.
        """
        query = _annotation_search_query(
            search_str=search_str,
            search_mode=search_mode,
            include_annotation_text=include_annotation_text,
            asp_ids=asp_ids,
        )
        if query is None:
            return []

        cursor = self.get_collection().find(query).sort("time_created", -1)

        if limit is not None:
            cursor = cursor.limit(limit)
        return list(cursor)

    def get_tier_stats_by_search(
        self,
        search_str: str,
        search_mode: str,
        include_annotation_text: bool,
        asp_ids: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """
        Return tier stats for the given search filter.

        Output shape:
        {
        "total":   {"tier1": int, "tier2": int, "tier3": int, "tier4": int},
        "by_assay": {
            "<assay>": {"tier1": int, "tier2": int, "tier3": int, "tier4": int},
            ...
        }
        }

        Rules:
        - Only docs with `class` are counted.
        - "Latest" is selected by `time_created` (descending).
        - Assay stats: dedupe per (assay + variant_key).
        - Total stats: dedupe per (variant_key) across assays (so no double counting).
        """

        if not search_str:
            return {"total": {"tier1": 0, "tier2": 0, "tier3": 0, "tier4": 0}, "by_assay": {}}

        query = _annotation_search_query(
            search_str=search_str,
            search_mode=search_mode,
            include_annotation_text=include_annotation_text,
            asp_ids=asp_ids,
        )
        if query is None:
            return {"total": {"tier1": 0, "tier2": 0, "tier3": 0, "tier4": 0}, "by_assay": {}}

        query["class"] = {"$exists": True, "$ne": None}

        # --- dedupe keys ---
        # total: dedupe across assays (avoid counting same variant multiple times)
        total_variant_key = {
            "nomenclature": "$nomenclature",
            "variant": "$variant",
            "gene": "$gene",
            "gene1": "$gene1",
            "gene2": "$gene2",
            "transcript": "$transcript",
        }

        # by_assay: dedupe within assay (same variant can be re-tiered in same assay)
        per_assay_variant_key = {
            "assay": "$assay",
            "nomenclature": "$nomenclature",
            "variant": "$variant",
            "gene": "$gene",
            "gene1": "$gene1",
            "gene2": "$gene2",
            "transcript": "$transcript",
        }

        def _tier_rollup_stage():
            """Tier rollup stage.

            Returns:
                    The  tier rollup stage result.
            """
            return [
                {
                    "$group": {
                        "_id": None,
                        "tier1": {"$sum": {"$cond": [{"$eq": ["$_id.class", 1]}, "$count", 0]}},
                        "tier2": {"$sum": {"$cond": [{"$eq": ["$_id.class", 2]}, "$count", 0]}},
                        "tier3": {"$sum": {"$cond": [{"$eq": ["$_id.class", 3]}, "$count", 0]}},
                        "tier4": {"$sum": {"$cond": [{"$eq": ["$_id.class", 4]}, "$count", 0]}},
                    }
                },
                {"$project": {"_id": 0, "tier1": 1, "tier2": 1, "tier3": 1, "tier4": 1}},
            ]

        col = self.get_collection()

        # -------------------------
        # (1) TOTAL stats (no double counting across assays)
        # -------------------------
        total_pipeline = [
            {"$match": query},
            {"$sort": {"variant": 1, "gene": 1, "time_created": -1}},
            {"$group": {"_id": total_variant_key, "class": {"$first": "$class"}}},
            {"$group": {"_id": {"class": "$class"}, "count": {"$sum": 1}}},
            *_tier_rollup_stage(),
        ]
        total_res = list(col.aggregate(total_pipeline))
        total_stats = (
            total_res[0] if total_res else {"tier1": 0, "tier2": 0, "tier3": 0, "tier4": 0}
        )

        # -------------------------
        # (2) ASSAY-specific stats
        # -------------------------
        by_assay_pipeline = [
            {"$match": query},
            {"$sort": {"assay": 1, "variant": 1, "gene": 1, "time_created": -1}},
            {"$group": {"_id": per_assay_variant_key, "class": {"$first": "$class"}}},
            {"$group": {"_id": {"assay": "$_id.assay", "class": "$class"}, "count": {"$sum": 1}}},
            # fold per assay into a single doc per assay
            {
                "$group": {
                    "_id": "$_id.assay",
                    "tier1": {"$sum": {"$cond": [{"$eq": ["$_id.class", 1]}, "$count", 0]}},
                    "tier2": {"$sum": {"$cond": [{"$eq": ["$_id.class", 2]}, "$count", 0]}},
                    "tier3": {"$sum": {"$cond": [{"$eq": ["$_id.class", 3]}, "$count", 0]}},
                    "tier4": {"$sum": {"$cond": [{"$eq": ["$_id.class", 4]}, "$count", 0]}},
                }
            },
            {
                "$project": {
                    "_id": 0,
                    "assay": "$_id",
                    "tier1": 1,
                    "tier2": 1,
                    "tier3": 1,
                    "tier4": 1,
                }
            },
            {"$sort": {"assay": 1}},
        ]
        by_assay_docs = list(col.aggregate(by_assay_pipeline))
        by_assay = defaultdict(
            lambda: {
                "tier1": 0,
                "tier2": 0,
                "tier3": 0,
                "tier4": 0,
            }
        )

        for d in by_assay_docs:
            if not d:
                assay = "Historic"
                tiers = {}
            else:
                assay = d.get("assay") or "Historic"
                tiers = d

            by_assay[assay]["tier1"] += tiers.get("tier1", 0) or 0
            by_assay[assay]["tier2"] += tiers.get("tier2", 0) or 0
            by_assay[assay]["tier3"] += tiers.get("tier3", 0) or 0
            by_assay[assay]["tier4"] += tiers.get("tier4", 0) or 0

        # Optional: convert back to normal dict
        by_assay = dict(by_assay)

        return {"total": total_stats, "by_assay": by_assay}
