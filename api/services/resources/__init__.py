"""Managed resource services."""

from .asp import AspService
from .aspc import AspcService, QueryProfileService
from .isgl import IsglService
from .sample import ResourceSampleService

__all__ = [
    "AspService",
    "AspcService",
    "IsglService",
    "QueryProfileService",
    "ResourceSampleService",
]
