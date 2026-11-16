# SPDX-FileCopyrightText: 2026 Ram Nanduri
# SPDX-License-Identifier: GPL-3.0-only

"""Translate public variant lookup failures into established application errors."""

from typing import Any

import httpx
from coyote.domain.common.errors import api_error

from coyote_mongo.knowledgebase.clinpgx_public import ClinPgxPublicClient
from coyote_mongo.knowledgebase.public_oncokb import PublicOncoKbClient


class PublicVariantLookups:
    """Bind external clients without exposing their HTTP exception types to the core."""

    def __init__(self, *, oncokb: PublicOncoKbClient, clinpgx: ClinPgxPublicClient) -> None:
        """Bind configured clients; construction does not make a network request."""
        self._oncokb, self._clinpgx = oncokb, clinpgx

    def oncokb(self, sample: dict[str, Any], variant: dict[str, Any]) -> dict[str, Any]:
        """Fetch public variant evidence, preserving safe upstream status and failure messages."""
        try:
            return dict(self._oncokb.annotate_variant(sample=sample, variant=variant))
        except httpx.HTTPStatusError as exc:
            raise api_error(
                exc.response.status_code,
                "Public OncoKB request failed",
                details=exc.response.text[:500],
            ) from exc
        except httpx.HTTPError as exc:
            raise api_error(
                502, "Public OncoKB is currently unavailable", details=str(exc)
            ) from exc

    def clinpgx(self, *, clinpgx_id: str | None, symbol: str | None) -> dict[str, Any]:
        """Fetch public gene context with the existing bounded failure translation."""
        try:
            return dict(self._clinpgx.get_gene_knowledge(clinpgx_id=clinpgx_id, symbol=symbol))
        except httpx.HTTPStatusError as exc:
            raise api_error(
                exc.response.status_code,
                "Public ClinPGx request failed",
                details=exc.response.text[:500],
            ) from exc
        except httpx.HTTPError as exc:
            raise api_error(
                502, "Public ClinPGx is currently unavailable", details=str(exc)
            ) from exc
