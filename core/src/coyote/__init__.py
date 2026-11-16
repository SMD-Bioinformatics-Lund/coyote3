# SPDX-FileCopyrightText: 2026 Ram Nanduri
# SPDX-License-Identifier: GPL-3.0-only

"""Reusable Coyote clinical application library, independent of the HTTP application.

Use ``coyote.application.operations`` for in-process application operations.
The independent ``coyote_pyclient`` distribution provides HTTP access. Importing this
package does not initialize database connections, workers, or a web application.
"""

from coyote.version import __version__

__all__ = ["__version__"]
