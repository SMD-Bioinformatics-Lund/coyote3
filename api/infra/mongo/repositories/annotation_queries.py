"""Pure annotation identity and search-query construction."""

from typing import Any
from urllib.parse import unquote

from bson import ObjectId

from api.infra.mongo.repository_utils import literal_text_query


def annotation_visibility_query(environment: str | None) -> dict[str, Any]:
    """Select namespaces permitted by the sample environment.

    Args:
        environment: Sample environment; production or None permits clinical records only.

    Returns:
        Production reads clinical records; nonproduction reads both namespaces.
    """
    if environment in (None, "production"):
        return {"namespace": "clinical"}
    if environment not in {"development", "testing", "validation"}:
        raise ValueError("Unrecognized annotation lookup environment")
    return {"namespace": {"$in": ["clinical", "sandboxed"]}}


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
    nomenclatures: list[str] | None = None,
) -> dict[str, Any] | None:
    """Build the annotation search query used by tiered-variant search."""
    if not search_str:
        return None

    exact = str(search_str).strip()
    gene_exact = exact.upper()
    diagnosis_exact = exact.lower()
    contains = literal_text_query(search_str, contains=True)
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
                {"gene": gene_exact},
                {"gene1": gene_exact},
                {"gene2": gene_exact},
            ]
        }
    elif mode == "transcript":
        query = {"$or": [{"transcript": exact}]}
    elif mode == "hgvsp":
        query = {"$or": [{"hgvsp": exact}]}
    elif mode == "hgvsc":
        query = {"$or": [{"hgvsc": exact}]}
    elif mode == "genomic":
        query = {"$or": [{"genomic": exact}, {"genomic_hash": exact}]}
    elif mode == "variant":
        query = {"$or": [{field: exact} for field in variant_fields]}
    elif mode == "author":
        query = {"author": contains}
    elif mode == "diagnosis":
        query = {"diagnosis_id": diagnosis_exact}
    elif mode == "annotation":
        query = {"text": contains}
    elif mode == "all":
        query = {
            "$or": [
                {"gene": gene_exact},
                {"transcript": exact},
                {"author": contains},
                {"diagnosis_id": diagnosis_exact},
                {"text": contains},
                {"gene1": gene_exact},
                {"gene2": gene_exact},
                *[{field: exact} for field in variant_fields],
            ]
        }
    else:
        return None

    query_parts = [query, {"namespace": "clinical"}]
    if not include_annotation_text and mode != "annotation":
        query_parts.append({"$or": [{"text": {"$exists": False}}, {"text": None}, {"text": ""}]})

    if asp_ids:
        query_parts.append({"asp_group": {"$in": asp_ids}})
    if nomenclatures:
        query_parts.append({"nomenclature": {"$in": nomenclatures}})

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

    for key in (
        "gene",
        "gene1",
        "gene2",
        "transcript",
        "asp_group",
        "diagnosis_id",
        "asp_id",
        "namespace",
    ):
        if annotation.get(key) is not None:
            query[key] = annotation.get(key)

    return query
