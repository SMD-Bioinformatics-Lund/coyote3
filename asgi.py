# SPDX-FileCopyrightText: 2026 Ram Nanduri
# SPDX-License-Identifier: GPL-3.0-only

"""ASGI entrypoint for Coyote4 FastAPI API."""

from coyote_api.app.main import app  # noqa: TID251

__all__ = ["app"]
