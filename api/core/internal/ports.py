"""Repository port for internal utility endpoints."""

from __future__ import annotations

from typing import Protocol


class InternalRepository(Protocol):
    def get_all_roles(self) -> list[dict]: ...
    def is_isgl_adhoc(self, isgl_id: str) -> bool: ...
    def get_isgl_display_name(self, isgl_id: str) -> str | None: ...
