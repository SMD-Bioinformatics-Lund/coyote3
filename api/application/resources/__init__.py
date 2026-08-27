"""Managed resource services."""

from .asp import AspService
from .aspc import AspcService
from .isgl import IsglService
from .sample import ResourceSampleService

__all__ = [
    "AspService",
    "AspcService",
    "IsglService",
    "ResourceSampleService",
]
