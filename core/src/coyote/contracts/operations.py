# SPDX-FileCopyrightText: 2026 Ram Nanduri
# SPDX-License-Identifier: GPL-3.0-only

"""Structured operation result contracts."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, computed_field


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
