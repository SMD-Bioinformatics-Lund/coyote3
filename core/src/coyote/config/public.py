# SPDX-FileCopyrightText: 2026 Ram Nanduri
# SPDX-License-Identifier: GPL-3.0-only

"""Explicit public metadata inputs accepted by the independent core."""

from pydantic import BaseModel, ConfigDict


class PublicSettings(BaseModel):
    """Remote reference-service availability, without backend credentials or endpoints for storage."""

    model_config = ConfigDict(frozen=True, extra="forbid", hide_input_in_errors=True)
    oncokb_configured: bool = False
    clinpgx_configured: bool = False
