"""Structured operation result contracts."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, computed_field


def _string_id(value: Any) -> str | None:
    """Convert database identifiers to JSON-safe strings."""
    if value is None:
        return None
    return str(value)


class OperationResult(BaseModel):
    """JSON-safe summary of a persistence mutation."""

    model_config = ConfigDict(frozen=True)

    acknowledged: bool = True
    matched_count: int = 0
    modified_count: int = 0
    deleted_count: int = 0
    inserted_count: int = 0
    requested_count: int = 0
    inserted_id: str | None = None
    upserted_id: str | None = None
    error: str | None = None

    @computed_field
    @property
    def ok(self) -> bool:
        """Return whether the operation was accepted and no local error occurred."""
        return bool(self.acknowledged and not self.error)

    def to_dict(self) -> dict[str, Any]:
        """Return a compact JSON-safe representation."""
        payload: dict[str, Any] = {"ok": self.ok, "acknowledged": self.acknowledged}
        for key in (
            "matched_count",
            "modified_count",
            "deleted_count",
            "inserted_count",
            "requested_count",
        ):
            value = getattr(self, key)
            if value:
                payload[key] = value
        if self.inserted_id is not None:
            payload["inserted_id"] = self.inserted_id
        if self.upserted_id is not None:
            payload["upserted_id"] = self.upserted_id
        if self.error:
            payload["error"] = self.error
        return payload

    @classmethod
    def empty(cls, *, requested_count: int = 0) -> "OperationResult":
        """Return a successful no-op result."""
        return cls(requested_count=int(requested_count or 0))

    @classmethod
    def failed(cls, error: str, *, requested_count: int = 0) -> "OperationResult":
        """Return a failed operation summary."""
        return cls(acknowledged=False, requested_count=int(requested_count or 0), error=error)

    @classmethod
    def from_update(cls, result: Any, *, requested_count: int = 1) -> "OperationResult":
        """Build from a Mongo update result."""
        return cls(
            acknowledged=bool(getattr(result, "acknowledged", True)),
            matched_count=int(getattr(result, "matched_count", 0) or 0),
            modified_count=int(getattr(result, "modified_count", 0) or 0),
            requested_count=int(requested_count or 0),
            upserted_id=_string_id(getattr(result, "upserted_id", None)),
        )

    @classmethod
    def from_delete(cls, result: Any, *, requested_count: int = 1) -> "OperationResult":
        """Build from a Mongo delete result."""
        return cls(
            acknowledged=bool(getattr(result, "acknowledged", True)),
            deleted_count=int(getattr(result, "deleted_count", 0) or 0),
            requested_count=int(requested_count or 0),
        )

    @classmethod
    def from_insert_one(cls, result: Any) -> "OperationResult":
        """Build from a Mongo insert-one result."""
        acknowledged = bool(getattr(result, "acknowledged", True))
        inserted_id = _string_id(getattr(result, "inserted_id", None))
        return cls(
            acknowledged=acknowledged,
            inserted_count=1 if acknowledged and inserted_id is not None else 0,
            requested_count=1,
            inserted_id=inserted_id,
        )

    @classmethod
    def from_insert_many(cls, result: Any, *, requested_count: int = 0) -> "OperationResult":
        """Build from a Mongo insert-many result."""
        inserted_ids = list(getattr(result, "inserted_ids", []) or [])
        return cls(
            acknowledged=bool(getattr(result, "acknowledged", True)),
            inserted_count=len(inserted_ids),
            requested_count=int(requested_count or len(inserted_ids)),
        )
