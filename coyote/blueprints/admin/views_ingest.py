"""Admin data-ingestion routes."""

from __future__ import annotations

import json

from flask import Response, abort, g, redirect, render_template, request, url_for
from flask import current_app as app
from flask_login import current_user, login_required

from coyote.blueprints.admin import admin_bp
from coyote.services.api_client import endpoints as api_endpoints
from coyote.services.api_client.api_client import (
    ApiRequestError,
    forward_headers,
    get_web_api_client,
)
from coyote.services.api_client.web import (
    flash_api_failure,
    flash_api_success,
    raise_page_load_error,
)


def _require_ingest_operator() -> None:
    """Allow ingestion workspace/actions only for developer-or-higher users."""
    role_levels = dict(getattr(app, "role_access_levels", {}) or {})
    required_level = role_levels.get("developer")
    if required_level is not None:
        if int(getattr(current_user, "access_level", 0) or 0) < int(required_level):
            abort(403)
        return
    role = str(getattr(current_user, "role", "") or "").strip().lower()
    if role not in {"developer", "admin"}:
        abort(403)


@admin_bp.route("/ingest", methods=["GET"])
@login_required
def ingest_workspace() -> str | Response:
    """Render ingestion workspace for sample-bundle and collection ingest flows."""
    _require_ingest_operator()
    try:
        payload = get_web_api_client().get_json(
            api_endpoints.internal("ingest", "collections"),
            headers=forward_headers(),
        )
        collections = sorted(payload.get("collections", []))
    except ApiRequestError as exc:
        raise_page_load_error(
            exc,
            logger=app.logger,
            log_message="Failed to load internal ingest collection catalog",
            summary="Unable to load ingestion workspace.",
        )
    return render_template("ingest/workspace.html", collections=collections)


@admin_bp.route("/ingest/sample-bundle/upload", methods=["POST"])
@login_required
def ingest_sample_bundle_upload() -> Response:
    """Upload YAML + referenced files and submit internal sample-bundle ingest."""
    _require_ingest_operator()
    yaml_file = request.files.get("yaml_file")
    if yaml_file is None or not yaml_file.filename:
        flash_api_failure("YAML file is required.", ApiRequestError("missing yaml file"))
        return redirect(url_for("admin_bp.ingest_workspace"))

    data_files = [f for f in request.files.getlist("data_files") if f and f.filename]
    increment = request.form.get("increment", "true").strip().lower() in {"1", "true", "yes", "on"}
    update_existing = request.form.get("update_existing", "false").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }

    files: list[tuple[str, tuple[str, object, str]]] = [
        (
            "yaml_file",
            (
                str(yaml_file.filename),
                yaml_file.stream,
                yaml_file.mimetype or "text/yaml",
            ),
        )
    ]
    for upload in data_files:
        files.append(
            (
                "data_files",
                (
                    str(upload.filename),
                    upload.stream,
                    upload.mimetype or "application/octet-stream",
                ),
            )
        )

    try:
        payload = get_web_api_client().post_multipart(
            api_endpoints.internal("ingest", "sample-bundle", "upload"),
            headers=forward_headers(),
            data={
                "increment": "true" if increment else "false",
                "update_existing": "true" if update_existing else "false",
            },
            files=files,
        )
        g.audit_metadata = {
            "sample_id": payload.get("sample_id"),
            "sample_name": payload.get("sample_name"),
        }
        flash_api_success(
            f"Sample ingest completed: {payload.get('sample_name')} ({payload.get('sample_id')})"
        )
    except ApiRequestError as exc:
        flash_api_failure("Sample bundle upload ingest failed.", exc)
    return redirect(url_for("admin_bp.ingest_workspace"))


@admin_bp.route("/ingest/collection", methods=["POST"])
@login_required
def ingest_collection_document() -> Response:
    """Insert or update one/many collection documents through internal ingest APIs."""
    _require_ingest_operator()
    collection = str(request.form.get("collection", "")).strip()
    mode = str(request.form.get("mode", "insert")).strip().lower()
    match_blob = (request.form.get("match_json") or "").strip()
    docs_blob = (request.form.get("documents_json") or "").strip()
    if not collection:
        flash_api_failure("Collection is required.", ApiRequestError("missing collection"))
        return redirect(url_for("admin_bp.ingest_workspace"))
    if not docs_blob:
        flash_api_failure("JSON payload is required.", ApiRequestError("missing json payload"))
        return redirect(url_for("admin_bp.ingest_workspace"))

    try:
        parsed_docs = json.loads(docs_blob)
    except json.JSONDecodeError as exc:
        flash_api_failure("Invalid JSON payload.", ApiRequestError(str(exc)))
        return redirect(url_for("admin_bp.ingest_workspace"))

    headers = forward_headers()
    client = get_web_api_client()

    try:
        if mode == "bulk":
            if not isinstance(parsed_docs, list):
                raise ApiRequestError("Bulk mode requires a JSON array in documents_json.")
            payload = client.post_json(
                api_endpoints.internal("ingest", "collection", "bulk"),
                headers=headers,
                json_body={
                    "collection": collection,
                    "documents": parsed_docs,
                    "ignore_duplicates": True,
                },
            )
            flash_api_success(
                f"Bulk insert complete for {collection}. Inserted: {payload.get('inserted_count', 0)}"
            )
        elif mode == "upsert":
            if not isinstance(parsed_docs, dict):
                raise ApiRequestError("Update mode requires a JSON object in documents_json.")
            if not match_blob:
                raise ApiRequestError("Update mode requires match_json.")
            try:
                match = json.loads(match_blob)
            except json.JSONDecodeError as exc:
                raise ApiRequestError(f"Invalid match JSON: {exc}") from exc
            if not isinstance(match, dict) or not match:
                raise ApiRequestError("match_json must be a non-empty JSON object.")
            payload = client.put_json(
                api_endpoints.internal("ingest", "collection"),
                headers=headers,
                json_body={
                    "collection": collection,
                    "match": match,
                    "document": parsed_docs,
                    "upsert": True,
                },
            )
            flash_api_success(
                "Collection update complete for "
                f"{collection}. matched={payload.get('matched_count', 0)} "
                f"modified={payload.get('modified_count', 0)}"
            )
        else:
            if not isinstance(parsed_docs, dict):
                raise ApiRequestError("Insert mode requires a JSON object in documents_json.")
            payload = client.post_json(
                api_endpoints.internal("ingest", "collection"),
                headers=headers,
                json_body={
                    "collection": collection,
                    "document": parsed_docs,
                    "ignore_duplicate": True,
                },
            )
            flash_api_success(
                f"Insert complete for {collection}. Inserted: {payload.get('inserted_count', 0)}"
            )
    except ApiRequestError as exc:
        flash_api_failure("Collection ingest operation failed.", exc)
    return redirect(url_for("admin_bp.ingest_workspace"))
