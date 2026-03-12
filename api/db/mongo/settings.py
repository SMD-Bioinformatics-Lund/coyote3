"""Mongo-specific settings helpers."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from api.config import get_mongo_settings

__all__ = ["get_mongo_settings"]
