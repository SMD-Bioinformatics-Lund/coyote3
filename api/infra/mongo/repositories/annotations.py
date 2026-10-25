"""
AnnotationsRepository module for Coyote3
=====================================

This module defines the `AnnotationsRepository` class used for accessing and managing
annotation data in MongoDB.

It is part of the MongoDB infrastructure layer.
"""

from copy import deepcopy
from typing import Any
from urllib.parse import unquote

from api.infra.mongo.repositories.annotation_queries import (
    _annotation_class_value,
    _annotation_object_id,
    _annotation_search_query,
    _classification_text_lookup_query,
    _small_variant_identity_clauses,
    _text_values,
    annotation_visibility_query,
)
from api.infra.mongo.repositories.annotation_statistics import AnnotationStatisticsMixin
from api.infra.mongo.repositories.base import BaseRepository
from api.infra.mongo.repository_utils import utc_now
from coyote3.application.common.execution_context import current_username
from coyote3.config.constants import DIAGNOSIS_BASE_ID
from coyote3.contracts.operations import OperationResult
from coyote3.contracts.schemas.registry import normalize_collection_document
from coyote3.domain.annotation_identity import (
    ANNOTATION_IDENTITY_FIELDS,
    annotation_context_fields,
    enrich_annotation_identity,
)
from coyote3.domain.annotation_scope import annotation_scope_match
from coyote3.domain.dna.variant_identity import build_simple_id


# -------------------------------------------------------------------------
# Class Definition
# -------------------------------------------------------------------------
class AnnotationsRepository(AnnotationStatisticsMixin, BaseRepository):
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
        col.create_index(
            [
                ("asp_id", 1),
                ("namespace", 1),
                ("diagnosis_id", 1),
                ("variant", 1),
                ("time_created", -1),
            ],
            name="annotation_scope_namespace",
            background=True,
        )
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
        col.create_index(
            [("transcript", 1), ("asp_group", 1), ("diagnosis_id", 1), ("time_created", -1)],
            name="transcript_group_diagnosis_time_created",
            background=True,
            sparse=True,
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
        group_path = [annotation["asp_group"]]
        group = self.adapter.assay_groups_collection.find_one({"group_id": group_path[0]})
        while group and group.get("parent_group_id") not in (None, *group_path):
            parent = group["parent_group_id"]
            group = self.adapter.assay_groups_collection.find_one({"group_id": parent})
            if not group or not group.get("is_active", True):
                break
            group_path.append(parent)
        for field in ("asp_group", "asp_id", "diagnosis_id", "namespace"):
            query.pop(field, None)
        query["asp_group"] = {"$in": group_path}
        query["diagnosis_id"] = {"$in": [annotation["diagnosis_id"], "base"]}
        environment = "production" if annotation["namespace"] == "clinical" else "testing"
        query.update(annotation_visibility_query(environment))
        candidates = []
        for row in self.get_collection().find(query).sort([("time_created", -1), ("_id", -1)]):
            match = annotation_scope_match(
                row,
                group_path=group_path,
                diagnosis=annotation["diagnosis_id"],
                context={"assay_id": annotation.get("asp_id"), "environment": environment},
            )
            if match["effective"] or match["fallback_eligible"]:
                candidates.append((row, match))
        candidates.sort(key=lambda item: (item[1]["scope_priority"], item[1]["diagnosis_priority"]))
        return candidates[0][0]["text"] if candidates else None

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
        result = OperationResult.from_insert_many(
            self.insert_many_atomic(annotations_copy),
            requested_count=len(annotations_copy),
        )
        if any(_annotation_class_value(item.get("class")) is not None for item in annotations_copy):
            self.invalidate_dashboard_metrics()
        return result

    def get_global_annotations(
        self, variant: dict, assay_group: str, diagnosis: str, *, sample_context: dict | None = None
    ) -> tuple:
        """
        Retrieve global annotations for a given variant, assay, and diagnosis.

        Match identity and visibility first. Exact assay, group, diagnosis and
        visible-namespace classifications are effective. Broader interpretations are
        ordered by specificity, including nearest biological ancestors, and
        require re-tiering before they can qualify for reporting.

        Args:
            variant (dict): A dictionary containing variant details, including
                            'CHROM', 'POS', 'REF', 'ALT', and 'INFO' with
                            'selected_CSQ' data.
            assay_group (str): The type of assay being used (e.g., 'solid').
            diagnosis (str): Exact diagnosis scope; null or blank selects Base.
            sample_context: Resolved assay and environment. Without context no
                classification is accepted as effective.

        Returns:
            tuple: A tuple containing:
                - annotations_arr (list): A list of all annotations.
                - latest_classification (dict): The latest classification for
                  the current assay.
                - latest_other_arr (list): A list of classifications for other
                  assays and diagnoses.
                - annotations_interesting (dict): A dictionary of annotations
                  deemed interesting based on assay and diagnosis.
        """
        diagnosis = diagnosis or DIAGNOSIS_BASE_ID
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

        if variant.get("nomenclature") in {"cn", "t"} and variant.get("variant"):
            annotations = (
                self.get_collection()
                .find(
                    {
                        "$and": [
                            {
                                "nomenclature": variant["nomenclature"],
                                "variant": variant["variant"],
                                **annotation_context_fields(
                                    nomenclature=variant["nomenclature"], source=variant
                                ),
                            },
                            annotation_visibility_query((sample_context or {}).get("environment")),
                        ]
                    }
                )
                .sort([("time_created", 1), ("_id", 1)])
            )
        elif selected_CSQ.get("SYMBOL") and identity_clauses:
            annotations = (
                self.get_collection()
                .find(
                    {
                        "$and": [
                            {"gene": selected_CSQ["SYMBOL"], "$or": identity_clauses},
                            annotation_visibility_query((sample_context or {}).get("environment")),
                        ]
                    }
                )
                .sort([("time_created", 1), ("_id", 1)])
            )
        elif "breakpoint1" in variant and "breakpoint2" in variant:
            fusion_query: dict[str, Any] = {
                "nomenclature": "f",
                "variant": f"{variant['breakpoint1']}^{variant['breakpoint2']}",
            }
            fusion_query.update(annotation_context_fields(nomenclature="f", source=variant))
            annotations = (
                self.get_collection()
                .find(
                    {
                        "$and": [
                            fusion_query,
                            annotation_visibility_query((sample_context or {}).get("environment")),
                        ]
                    }
                )
                .sort([("time_created", 1), ("_id", 1)])
            )
        else:
            annotations = []

        group_path = [assay_group]
        group = self.adapter.assay_groups_collection.find_one({"group_id": assay_group})
        while isinstance(group, dict) and group.get("parent_group_id"):
            parent = group["parent_group_id"]
            if parent in group_path:
                break
            group = self.adapter.assay_groups_collection.find_one({"group_id": parent})
            if not isinstance(group, dict) or not group.get("is_active", True):
                break
            group_path.append(parent)

        latest_classification = {"class": 999}
        latest_classification_other = {}
        annotations_arr = []
        text_candidates = []
        for anno in annotations:
            match = annotation_scope_match(
                anno, group_path=group_path, diagnosis=diagnosis, context=sample_context or {}
            )
            anno_class = _annotation_class_value(anno.get("class"))
            if anno_class is not None:
                if match["effective"]:
                    latest_classification = anno
                else:
                    scope = (anno["asp_group"], anno["diagnosis_id"], anno.get("asp_id"))
                    latest_classification_other.pop(scope, None)
                    latest_classification_other[scope] = {
                        **anno,
                        **match,
                    }
            if anno.get("text") is not None:
                annotations_arr.append(anno)
                if match["effective"] or match["fallback_eligible"]:
                    text_candidates.append((anno, match))

        # Oldest-first query order makes reverse order newest-first. Stable
        # scope sorting then preserves recency only within equal specificity.
        latest_other_arr = list(reversed(latest_classification_other.values()))
        latest_other_arr.sort(
            key=lambda row: (
                not row["fallback_eligible"],
                row["scope_priority"],
                row["diagnosis_priority"],
            )
        )
        text_candidates.reverse()
        text_candidates.sort(
            key=lambda item: (item[1]["scope_priority"], item[1]["diagnosis_priority"])
        )
        annotations_interesting = {}
        if text_candidates:
            annotations_interesting[f"{assay_group}:{diagnosis}"] = text_candidates[0][0]

        return (
            annotations_arr,
            latest_classification,
            latest_other_arr,
            annotations_interesting,
        )

    def get_latest_transcript_classifications(
        self,
        variant: dict[str, Any],
        transcripts: list[dict[str, Any]],
        assay_group: str,
        diagnosis: str | None,
        *,
        sample_context: dict | None = None,
    ) -> dict[str, dict[str, Any]]:
        """Return the newest classification for each exact alternate transcript."""
        genomic = variant.get("simple_id")
        if not genomic and all(key in variant for key in ("CHROM", "POS", "REF", "ALT")):
            genomic = build_simple_id(
                variant["CHROM"], variant["POS"], variant["REF"], variant["ALT"]
            )

        transcript_clauses: list[dict[str, Any]] = []
        for transcript in transcripts:
            feature = str(transcript.get("Feature") or "").strip()
            gene = str(transcript.get("SYMBOL") or "").strip()
            identities = _small_variant_identity_clauses(
                hgvsp=transcript.get("HGVSp"),
                hgvsc=transcript.get("HGVSc"),
                genomic=genomic,
            )
            if not feature or not gene or not identities:
                continue
            transcript_clauses.append(
                {
                    "transcript": feature,
                    "gene": gene,
                    "$or": identities,
                }
            )

        if not transcript_clauses:
            return {}

        query: dict[str, Any] = {
            "asp_group": assay_group,
            "class": {"$in": [1, 2, 3, 4]},
            "$or": transcript_clauses,
        }
        query["diagnosis_id"] = diagnosis or DIAGNOSIS_BASE_ID
        if not sample_context:
            return {}
        query["asp_id"] = sample_context["assay_id"]
        query.update(annotation_visibility_query(sample_context["environment"]))

        latest_by_transcript: dict[str, dict[str, Any]] = {}
        annotations = self.get_collection().find(query).sort([("time_created", -1), ("_id", -1)])
        for annotation in annotations:
            feature = str(annotation.get("transcript") or "").strip()
            if feature and feature not in latest_by_transcript:
                latest_by_transcript[feature] = annotation
        return latest_by_transcript

    def get_additional_classifications(
        self, variant: dict, assay_group: str, diagnosis: str, *, sample_context: dict | None = None
    ) -> list:
        """
        Retrieve additional classifications for a given variant based on specified assay and diagnosis.
        This method constructs a query to search for classifications in the database that match the
        provided variant's genes, transcripts, and nomenclature variants (HGVSp and HGVSc). If the
        sample's diagnosis is always matched exactly, including Base.
        Args:
            variant (dict): A dictionary containing variant details including 'transcripts', 'HGVSp',
                            'HGVSc', and 'genes'.
            assay_group (str): The type of assay being used (e.g., 'solid').
            diagnosis (str): Exact scope; null or blank selects Base.
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
                "asp_group": assay_group,
                "class": {"$in": [1, 2, 3, 4]},
            }
        else:
            query = {
                "nomenclature": "f",
                "variant": f"{breakpoint1}^{breakpoint2}",
                "asp_group": assay_group,
                "class": {"$in": [1, 2, 3, 4]},
            }
            query.update(annotation_context_fields(nomenclature="f", source=variant))
        query["diagnosis_id"] = diagnosis or DIAGNOSIS_BASE_ID
        if not sample_context:
            return []
        query["asp_id"] = sample_context["assay_id"]
        query.update(annotation_visibility_query(sample_context["environment"]))

        return list(
            self.get_collection().find(query).sort([("time_created", -1), ("_id", -1)]).limit(1)
        )

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
        The document includes details such as the variant, nomenclature, classification, assay, diagnosis, and additional
        metadata like the author and creation time.

        Args:
            variant (str): The variant identifier (e.g., genomic location or variant ID).
            nomenclature (str): The nomenclature type ('p', 'c', 'g', or 'f').
            class_num (int): The classification number assigned to the variant.
            variant_data (dict): A dictionary containing additional variant details, such as:
                - asp_group (str): Biological group identifier.
                - asp_id (str | None): Assay identifier, or null for group scope.
                - namespace (str): Clinical or sandboxed interpretation scope.
                - diagnosis_id (str): Diagnosis identifier.
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
            "created_by": current_username("") or None,
            "updated_by": current_username("") or None,
            "time_created": utc_now(),
            "variant": variant,
            "nomenclature": nomenclature,
            "asp_group": variant_data.get("asp_group"),
            "asp_id": variant_data.get("asp_id"),
            "diagnosis_id": variant_data.get("diagnosis_id"),
            "namespace": variant_data.get("namespace"),
        }

        if "text" in kwargs:
            document["text"] = kwargs["text"]
        else:
            document["class"] = class_num

        document.update(annotation_context_fields(nomenclature=nomenclature, source=variant_data))

        document = enrich_annotation_identity(document, source=variant_data)
        document = normalize_collection_document("annotation", document)
        result = OperationResult.from_insert_one(self.get_collection().insert_one(document))
        if _annotation_class_value(document.get("class")) is not None:
            self.invalidate_dashboard_metrics()
        return result

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
        Deletion is limited to the exact assay, diagnosis, nomenclature, and
        finding context supplied by the current workflow.

        Args:
            variant (str): The variant identifier (e.g., genomic location or variant ID).
            nomenclature (str): The nomenclature type ('p', 'c', 'g', or 'f').
            variant_data (dict): A dictionary containing additional variant details, such as:
                - asp_group (str): Biological group identifier.
                - asp_id (str | None): Assay identifier, or null for group scope.
                - namespace (str): Clinical or sandboxed interpretation scope.
                - diagnosis_id (str): Diagnosis identifier.
                - gene (str): The gene symbol (if applicable).

        Returns:
            A structured write result for the scoped deletion.
        """
        query = {
            "variant": variant,
            "asp_group": variant_data.get("asp_group"),
            "nomenclature": nomenclature,
            "diagnosis_id": variant_data.get("diagnosis_id"),
            **annotation_context_fields(nomenclature=nomenclature, source=variant_data),
        }

        class_filter: dict = {"class": {"$exists": True}}
        if class_num is not None:
            class_filter["class"] = class_num

        delete_clause: list[dict] = [class_filter]
        if annotation_text:
            delete_clause.append({"text": annotation_text})

        scoped_query = {**query, "$or": delete_clause}
        scoped_query["asp_id"] = variant_data["asp_id"]
        scoped_query["namespace"] = variant_data["namespace"]
        result = OperationResult.from_delete(self.delete_many_atomic(scoped_query))
        if result.deleted_count:
            self.invalidate_dashboard_metrics()
        return result

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
        return (
            self.get_collection()
            .find({"gene": gene_name, "namespace": "clinical"})
            .sort("time_created", 1)
        )

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

    def find_variants_by_search_string(
        self,
        search_str: str,
        search_mode: str,
        include_annotation_text: bool,
        asp_ids: list | None = None,
        nomenclatures: list[str] | None = None,
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
            search_mode (str): The mode of search, can be 'gene', 'transcript', 'variant', 'author', or 'diagnosis'.
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
            nomenclatures=nomenclatures,
        )
        if query is None:
            return []

        cursor = self.get_collection().find(query).sort("time_created", -1)

        if limit is not None:
            cursor = cursor.limit(limit)
        return list(cursor)
