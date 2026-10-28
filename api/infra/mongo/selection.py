"""Translate application selection expressions to MongoDB predicates."""

from collections.abc import Mapping
from typing import Any

from bson import ObjectId

from api.infra.mongo.persistence import to_provider_id
from coyote3.domain.selection import Operator, RecordField, Selection

_OPERATORS = {
    Operator.ALL: "$and",
    Operator.ANY: "$or",
    Operator.NONE: "$nor",
    Operator.NOT: "$not",
    Operator.EQUAL: "$eq",
    Operator.NOT_EQUAL: "$ne",
    Operator.GREATER: "$gt",
    Operator.AT_LEAST: "$gte",
    Operator.LESS: "$lt",
    Operator.AT_MOST: "$lte",
    Operator.IN: "$in",
    Operator.NOT_IN: "$nin",
    Operator.PRESENT: "$exists",
    Operator.VALUE_TYPE: "$type",
    Operator.ELEMENT: "$elemMatch",
    Operator.PATTERN: "$regex",
    Operator.PATTERN_OPTIONS: "$options",
    Operator.CONTAINS_ALL: "$all",
    Operator.LENGTH: "$size",
    Operator.MODULO: "$mod",
    Operator.BITS_ALL_SET: "$bitsAllSet",
    Operator.BITS_ANY_SET: "$bitsAnySet",
    Operator.BITS_ALL_CLEAR: "$bitsAllClear",
    Operator.BITS_ANY_CLEAR: "$bitsAnyClear",
}
_FIELDS = {
    RecordField.IDENTITY: "_id",
    RecordField.SAMPLE: "SAMPLE_ID",
    RecordField.ANNOTATION_REFERENCE: "annotation_oid",
    RecordField.ANNOTATION_TEXT_REFERENCE: "annotation_text_oid",
}


def compile_selection(
    selection: Selection, *, field_names: Mapping[str, str] | None = None
) -> dict[str, Any]:
    """Translate a validated application selection without mutating its clinical intent.

    Args:
        selection: Explicit neutral selection supplied by a repository caller.
        field_names: Adapter-owned clinical-to-storage field bindings. None uses the
            established document representation. Prefix bindings also map descendants.

    Returns:
        A fresh MongoDB predicate preserving grouping, operand types and array semantics.

    Raises:
        TypeError: A caller supplies an untyped predicate instead of a selection.
        ValueError: A nested binding crosses its containing array/object boundary.
    """
    if not isinstance(selection, Selection):
        raise TypeError("Repository selection must be a Selection value")
    criteria = _bind_fields(selection.criteria, field_names) if field_names else selection.criteria
    return _compile(criteria)


def _storage_path(path: str, bindings: Mapping[str, str]) -> str:
    """Resolve the most specific adapter binding for a clinical field path.

    Args:
        path: Full clinical path, including any containing array path.
        bindings: Trusted clinical-to-storage paths supplied by the adapter.

    Returns:
        Mapped path with its unmatched suffix retained, or the original path.
    """
    ancestors = [key for key in bindings if path == key or path.startswith(key + ".")]
    if not ancestors:
        return path
    selected = max(ancestors, key=len)
    return bindings[selected] + path[len(selected) :]


def _bind_fields(value: Any, bindings: Mapping[str, str], prefix: str = "") -> Any:
    """Map selection paths while preserving literals and nested array semantics.

    Args:
        value: Neutral selection nodes; literal comparison values are retained unchanged.
        bindings: Trusted field mappings owned by the concrete repository adapter.
        prefix: Clinical path of a containing field; empty denotes the root record.

    Returns:
        New predicate containers with physical field paths and neutral operators.

    Raises:
        ValueError: A field inside an element match maps outside that collection.
    """
    if isinstance(value, Selection):
        return _bind_fields(value.criteria, bindings, prefix)
    if isinstance(value, (list, tuple)):
        return [_bind_fields(item, bindings, prefix) for item in value]
    if not isinstance(value, Mapping):
        return value
    result = {}
    groups = {Operator.ALL, Operator.ANY, Operator.NONE, Operator.NOT, Operator.ELEMENT}
    for key, operand in value.items():
        if isinstance(key, Operator):
            result[key] = _bind_fields(operand, bindings, prefix) if key in groups else operand
        elif isinstance(key, RecordField):
            result[key] = operand
        else:
            clinical = f"{prefix}.{key}" if prefix else key
            physical = _storage_path(clinical, bindings)
            if prefix:
                parent = _storage_path(prefix, bindings) + "."
                if not physical.startswith(parent):
                    raise ValueError("A nested field binding cannot cross its containing record")
                physical = physical[len(parent) :]
            literal_object = isinstance(operand, Mapping) and all(
                isinstance(child, str) for child in operand
            )
            result[physical] = (
                operand if literal_object else _bind_fields(operand, bindings, clinical)
            )
    return result


def _compile(value: Any) -> Any:
    """Render expression nodes recursively at the persistence boundary.

    Args:
        value: A selection, comparison mapping, operand collection or scalar.

    Returns:
        Fresh query containers using MongoDB operators and physical identity paths;
        scalar clinical operands retain their values.
    """
    if isinstance(value, Selection):
        return _compile(value.criteria)
    if isinstance(value, Mapping):
        result = {}
        for key, item in value.items():
            name = (
                _OPERATORS[key]
                if isinstance(key, Operator)
                else _FIELDS[key]
                if isinstance(key, RecordField)
                else key
            )
            if key in (RecordField.ANNOTATION_REFERENCE, RecordField.ANNOTATION_TEXT_REFERENCE):
                result[name] = _annotation_references(item)
            elif key is RecordField.IDENTITY:
                result[name] = _identity_comparison(item)
            else:
                result[name] = _compile(item)
        return result
    if isinstance(value, (tuple, list)):
        return [_compile(item) for item in value]
    return value


def _identity_comparison(value: Any) -> Any:
    """Restore native identifiers only for comparisons on the physical document identity.

    Args:
        value: Scalar identity or typed comparisons on logical identity values.

    Returns:
        Provider-native equality/membership operands, leaving presence/type tests intact.
    """
    if not isinstance(value, Mapping):
        return to_provider_id(value)
    result = {}
    for operator, operand in value.items():
        if operator in {Operator.IN, Operator.NOT_IN}:
            result[_OPERATORS[operator]] = [to_provider_id(item) for item in operand]
        elif operator in {Operator.EQUAL, Operator.NOT_EQUAL}:
            result[_OPERATORS[operator]] = to_provider_id(operand)
        else:
            result[_OPERATORS[operator]] = _compile(operand)
    return result


def _annotation_references(value: Any) -> dict[str, Any]:
    """Match the existing serialized and native representations of annotation references.

    Args:
        value: Membership comparison on canonical string annotation identifiers.

    Returns:
        Predicate admitting both supported persisted reference representations.

    Raises:
        ValueError: A caller requests an unsupported reference comparison.
    """
    if not isinstance(value, Mapping) or set(value) != {Operator.IN}:
        raise ValueError("Annotation references require an explicit membership comparison")
    identifiers = value[Operator.IN]
    return {
        "$in": [
            reference
            for identifier in identifiers
            for reference in (
                [ObjectId(identifier), identifier]
                if ObjectId.is_valid(identifier)
                else [identifier]
            )
        ]
    }
