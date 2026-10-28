"""Database-independent selection expressions passed to repository ports.

Field paths address the application's clinical record vocabulary. Operators are
domain values, never executable database syntax. Storage adapters translate these
expressions to their own query language and map logical identity fields.
"""

from collections.abc import Mapping
from datetime import date, datetime
from enum import Enum
from re import Pattern
from types import MappingProxyType
from typing import Any, cast

from pydantic import BaseModel, ConfigDict, field_validator, model_serializer


class Operator(Enum):
    """Supported logical, scalar and collection comparisons for clinical selections."""

    ALL = "all_of"
    ANY = "any_of"
    NONE = "none_of"
    NOT = "not"
    EQUAL = "equal"
    NOT_EQUAL = "not_equal"
    GREATER = "greater_than"
    AT_LEAST = "at_least"
    LESS = "less_than"
    AT_MOST = "at_most"
    IN = "in_values"
    NOT_IN = "not_in_values"
    PRESENT = "present"
    VALUE_TYPE = "value_type"
    ELEMENT = "matching_element"
    PATTERN = "pattern"
    PATTERN_OPTIONS = "pattern_options"
    CONTAINS_ALL = "contains_all"
    LENGTH = "length"
    MODULO = "modulo"
    BITS_ALL_SET = "bits_all_set"
    BITS_ANY_SET = "bits_any_set"
    BITS_ALL_CLEAR = "bits_all_clear"
    BITS_ANY_CLEAR = "bits_any_clear"


class RecordField(Enum):
    """Logical identities whose physical storage names are adapter-owned."""

    IDENTITY = "identity"
    SAMPLE = "sample_identity"
    ANNOTATION_REFERENCE = "annotation_reference"
    ANNOTATION_TEXT_REFERENCE = "annotation_text_reference"


Criteria = dict[str | Operator | RecordField, Any]


def comparison_operator(name: str) -> Operator:
    """Resolve a validated clinical condition operator to a neutral comparison.

    Args:
        name: Operator registered by the clinical condition catalog.

    Returns:
        Its selection-language operator.

    Raises:
        ValueError: The comparison has no supported selection semantics.
    """
    operators = {
        "eq": Operator.EQUAL,
        "ne": Operator.NOT_EQUAL,
        "gt": Operator.GREATER,
        "gte": Operator.AT_LEAST,
        "lt": Operator.LESS,
        "lte": Operator.AT_MOST,
        "in": Operator.IN,
        "nin": Operator.NOT_IN,
        "exists": Operator.PRESENT,
        "type": Operator.VALUE_TYPE,
        "regex": Operator.PATTERN,
        "all": Operator.CONTAINS_ALL,
        "size": Operator.LENGTH,
        "mod": Operator.MODULO,
        "bitsAllSet": Operator.BITS_ALL_SET,
        "bitsAnySet": Operator.BITS_ANY_SET,
        "bitsAllClear": Operator.BITS_ALL_CLEAR,
        "bitsAnyClear": Operator.BITS_ANY_CLEAR,
    }
    if name not in operators:
        raise ValueError(f"Unsupported comparison: {name}")
    return operators[name]


def _freeze(value: Any) -> Any:
    """Copy expression values into immutable, provider-independent containers.

    Args:
        value: Clinical field names, comparison nodes, scalar operands or nested selections.

    Returns:
        An immutable expression value without references to caller-owned containers.

    Raises:
        ValueError: A field uses executable storage syntax or a value is provider-specific.
    """
    if isinstance(value, Selection):
        return value
    if isinstance(value, Mapping):
        for key in value:
            if not isinstance(key, (str, Operator, RecordField)):
                raise ValueError("Selection keys must be field paths or registered operators")
            if isinstance(key, str) and (key.startswith("$") or key in {"_id", "SAMPLE_ID"}):
                raise ValueError("Storage syntax and physical identity fields are not selections")
        return MappingProxyType({key: _freeze(item) for key, item in value.items()})
    if isinstance(value, (list, tuple)):
        return tuple(_freeze(item) for item in value)
    if value is None or isinstance(value, (str, bool, int, float, date, datetime, Pattern)):
        return value
    raise ValueError(
        f"Selection operand is not a supported application value: {type(value).__name__}"
    )


def selection_data(value: Any) -> Any:
    """Describe selections as neutral data for logs and offline tooling.

    Args:
        value: Selection, expression container or scalar operand.

    Returns:
        Independent containers with descriptive operator and logical identity names.
    """
    if isinstance(value, Selection):
        return selection_data(value.criteria)
    if isinstance(value, Mapping):
        return {
            key.value if isinstance(key, (Operator, RecordField)) else key: selection_data(item)
            for key, item in value.items()
        }
    if isinstance(value, (list, tuple)):
        return [selection_data(item) for item in value]
    if isinstance(value, Pattern):
        return {"pattern": value.pattern, "flags": value.flags}
    return value


class Selection(BaseModel):
    """Carry an immutable clinical selection to a repository without driver objects."""

    model_config = ConfigDict(frozen=True, arbitrary_types_allowed=True)

    criteria: Mapping[Any, Any]

    @field_validator("criteria", mode="after")
    @classmethod
    def _immutable_criteria(cls, value: Mapping[Any, Any]) -> Mapping[Any, Any]:
        """Freeze field comparisons after validating the outer mapping."""
        return cast(Mapping[Any, Any], _freeze(value))

    @model_serializer
    def _serialize(self) -> dict[str, Any]:
        """Expose descriptive selection data without a database query dialect."""
        return {"criteria": selection_data(self)}

    def __bool__(self) -> bool:
        """Return whether this selection restricts any application fields."""
        return bool(self.criteria)

    def __deepcopy__(self, memo: dict[int, Any] | None = None) -> "Selection":
        """Reuse an immutable selection when copying surrounding workflow state."""
        return self


def select(criteria: Mapping[Any, Any] | Selection) -> Selection:
    """Build a repository selection from application comparisons.

    Args:
        criteria: Neutral field comparisons, or an already immutable selection.

    Returns:
        An independent immutable selection, reusing an already validated value.

    Raises:
        ValueError: A comparison contains physical query syntax or provider objects.
    """
    return criteria if isinstance(criteria, Selection) else Selection(criteria=criteria)
