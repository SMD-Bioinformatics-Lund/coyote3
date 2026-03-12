"""Shared HTTP-layer helpers for the API."""

from __future__ import annotations

from copy import deepcopy

from fastapi import HTTPException

from api.extensions import store, util


def api_error(status_code: int, message: str) -> HTTPException:
    return HTTPException(
        status_code=status_code,
        detail={"status": status_code, "error": message, "details": None},
    )


def get_formatted_assay_config(sample: dict):
    assay_config = store.aspc_handler.get_aspc_no_meta(
        sample.get("assay"), sample.get("profile", "production")
    )
    if not assay_config:
        return None
    schema_name = assay_config.get("schema_name")
    assay_config_schema = store.schema_handler.get_schema(schema_name)
    return util.common.format_assay_config(deepcopy(assay_config), assay_config_schema)
