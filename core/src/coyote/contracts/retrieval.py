# SPDX-FileCopyrightText: 2026 Ram Nanduri
# SPDX-License-Identifier: GPL-3.0-only

"""Bounded, database-independent resource metadata retrieval contracts."""

from datetime import datetime
from enum import StrEnum
from typing import Annotated, Any, Literal, get_args, get_origin

from pydantic import BaseModel, ConfigDict, Field, StrictBool, StrictInt, StrictStr, model_validator

from coyote.contracts.resource_metadata import (
    AssayMetadata,
    ConfigurationMetadata,
    DiagnosisMetadata,
    GeneListMetadata,
    GroupMetadata,
    ResourceMetadata,
    SampleMetadata,
)


class ReadResource(StrEnum):
    """Named public resources, independent of physical collection names."""

    ASP = "asp"
    ASPC = "aspc"
    SAMPLES = "samples"
    ISGL = "isgl"
    ASSAY_GROUPS = "assay-groups"
    DIAGNOSES = "diagnoses"


RESOURCE_MODELS: dict[ReadResource, type[ResourceMetadata]] = {
    ReadResource.ASP: AssayMetadata,
    ReadResource.ASPC: ConfigurationMetadata,
    ReadResource.SAMPLES: SampleMetadata,
    ReadResource.ISGL: GeneListMetadata,
    ReadResource.ASSAY_GROUPS: GroupMetadata,
    ReadResource.DIAGNOSES: DiagnosisMetadata,
}
RESOURCE_IDENTIFIERS: dict[ReadResource, str] = {
    ReadResource.ASP: "asp_id",
    ReadResource.ASPC: "aspc_id",
    ReadResource.SAMPLES: "name",
    ReadResource.ISGL: "isgl_id",
    ReadResource.ASSAY_GROUPS: "group_id",
    ReadResource.DIAGNOSES: "diagnosis_id",
}

FilterScalar = (
    Annotated[StrictStr, Field(max_length=512)] | StrictBool | StrictInt | datetime | None
)


class FieldPredicate(BaseModel):
    """Supported comparisons; supplied operators combine with AND.

    Equality with null matches explicitly null values, not absent fields. Equality
    and membership on an array field compare its elements. Ranges accept integer
    and timestamp fields only. No arbitrary database operators are accepted.
    """

    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)

    eq: FilterScalar = None
    one_of: Annotated[list[FilterScalar], Field(min_length=1, max_length=100)] | None = Field(
        default=None, alias="in"
    )
    gte: FilterScalar = None
    lte: FilterScalar = None

    @model_validator(mode="after")
    def require_comparisons(self) -> "FieldPredicate":
        """Reject empty predicates and null ranges or membership arrays."""
        if not self.model_fields_set:
            raise ValueError("A predicate must contain at least one comparison")
        if "one_of" in self.model_fields_set and self.one_of is None:
            raise ValueError("in requires a nonempty array")
        for key in ("gte", "lte"):
            if key in self.model_fields_set and getattr(self, key) is None:
                raise ValueError("Range bounds cannot be null")
        return self


class ResourceReadQuery(BaseModel):
    """Request a bounded page, aggregate, or selected metadata fields.

    Filters, projections and ordering are checked against the named resource's
    metadata schema by validate_resource. Related records are available only for
    sample list reads, and require their own access permissions.
    """

    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)

    operation: Literal["list", "ids", "count", "exists", "distinct"] = "list"
    filters: Annotated[dict[str, FilterScalar | FieldPredicate], Field(max_length=20)] = Field(
        default_factory=dict
    )
    fields: Annotated[list[str], Field(min_length=1, max_length=30)] | None = None
    sort: str | None = None
    descending: StrictBool = False
    page: Annotated[StrictInt, Field(ge=1, le=10000)] = 1
    per_page: Annotated[StrictInt, Field(ge=1, le=200)] = 50
    field: str | None = None
    include: Annotated[list[Literal["assay", "configuration"]], Field(max_length=2)] = Field(
        default_factory=list
    )

    related_filters: dict[
        Literal["assay", "configuration"],
        Annotated[dict[str, FilterScalar | FieldPredicate], Field(min_length=1, max_length=20)],
    ] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_operation(self) -> "ResourceReadQuery":
        """Reject options with no meaning for the requested operation."""
        if (self.operation == "distinct") != (self.field is not None):
            raise ValueError("field is required only for distinct")
        if self.operation != "list" and (self.fields is not None or self.include):
            raise ValueError("fields and include are supported only for list")
        if self.operation in {"ids", "distinct", "count", "exists"} and self.sort is not None:
            raise ValueError("sort is supported only for list; value pages sort by value")
        if len(self.include) != len(set(self.include)):
            raise ValueError("include must not repeat a relationship")
        if self.fields is not None and len(self.fields) != len(set(self.fields)):
            raise ValueError("fields must not repeat a field")
        return self

    def validate_resource(self, resource: ReadResource) -> "ResourceReadQuery":
        """Validate names and types, returning normalized timestamp predicates.

        Args:
            resource: Public resource whose metadata defines the field allowlist.

        Returns:
            A validated query with ISO timestamp strings converted to datetimes.

        Raises:
            ValueError: A field, relationship, comparison or value type is unsupported.
        """
        schema = RESOURCE_MODELS[resource].model_fields
        requested = set(self.filters) | set(self.fields or [])
        requested.update(item for item in (self.sort, self.field) if item is not None)
        unknown = requested - schema.keys()
        if unknown:
            raise ValueError(f"Unsupported {resource.value} fields: {', '.join(sorted(unknown))}")
        if (self.include or self.related_filters) and resource != ReadResource.SAMPLES:
            raise ValueError("include and related_filters are supported only for samples")
        if self.sort and get_origin(get_args(schema[self.sort].annotation)[0]) is list:
            raise ValueError("Sorting by array fields is not supported")
        normalized = {}
        for name, supplied in self.filters.items():
            predicate = (
                supplied if isinstance(supplied, FieldPredicate) else FieldPredicate(eq=supplied)
            )
            expected = get_args(schema[name].annotation)[0]
            array_field = get_origin(expected) is list
            scalar_type = get_args(expected)[0] if array_field else expected
            values = predicate.model_dump(exclude_unset=True, by_alias=True)
            for operator, value in values.items():
                if operator in {"gte", "lte"} and (
                    array_field or scalar_type not in {int, datetime}
                ):
                    raise ValueError(f"Ranges are not supported for {name}")
                candidates = value if operator == "in" else [value]
                converted = []
                for candidate in candidates:
                    if (
                        candidate is not None
                        and scalar_type is datetime
                        and isinstance(candidate, str)
                    ):
                        try:
                            candidate = datetime.fromisoformat(candidate.replace("Z", "+00:00"))
                        except ValueError as exc:
                            raise ValueError(f"{name} requires an ISO timestamp") from exc
                    if candidate is not None and type(candidate) is not scalar_type:
                        raise ValueError(f"{name} requires {scalar_type.__name__} values")
                    converted.append(candidate)
                values[operator] = converted if operator == "in" else converted[0]
            if "gte" in values and "lte" in values:
                try:
                    if values["gte"] > values["lte"]:
                        raise ValueError(f"{name} lower bound exceeds its upper bound")
                except TypeError as exc:
                    raise ValueError(
                        "Timestamp bounds must use matching timezone conventions"
                    ) from exc
            normalized[name] = FieldPredicate.model_validate(values)
        related = {}
        for relationship, filters in self.related_filters.items():
            target = ReadResource.ASP if relationship == "assay" else ReadResource.ASPC
            related[relationship] = (
                ResourceReadQuery(filters=filters).validate_resource(target).filters
            )
        return self.model_copy(update={"filters": normalized, "related_filters": related})


class ResourceReadPage(BaseModel):
    """Metadata or scalar page, with aggregates populated only when requested."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    items: list[Any] = Field(default_factory=list)
    total: int = 0
    page: int = 1
    per_page: int = 50
    has_next: bool = False
    count: int | None = None
    exists: bool | None = None
