# SPDX-FileCopyrightText: 2026 Ram Nanduri
# SPDX-License-Identifier: GPL-3.0-only

"""Health and docs router."""

from __future__ import annotations

from fastapi import APIRouter

from coyote_api.contracts.system import HealthPayload
from coyote_api.interfaces.http.tags import TAG_SYSTEM

router = APIRouter(tags=[TAG_SYSTEM])


@router.get("/api/v1/health", response_model=HealthPayload)
def health():
    """Return a lightweight health-check payload."""
    return {"status": "ok"}
