"""Typed configuration inputs and software defaults for application operations.

Hosts can select one immutable center profile with ``configure_center`` before
importing application operations. This package does not discover environment
files, credentials, database endpoints or an external center directory.
"""

from coyote3.config.selection import CenterConfiguration, configure_center

__all__ = ["CenterConfiguration", "configure_center"]
