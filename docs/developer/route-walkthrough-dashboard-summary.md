# Route Walkthrough: Dashboard Summary

This page shows one concrete end-to-end flow, from UI route to API to DB and back.

## Scenario

User opens dashboard in UI. Flask fetches summary from FastAPI, FastAPI builds payload from service/repository, response is rendered in template.

## Step 1: UI route handler (Flask)

File: `coyote/blueprints/dashboard/views.py`

```python
payload = get_web_api_client().get_json(
    api_endpoints.dashboard("summary"),
    headers=forward_headers(),
)
```

What this does:

- Builds API path via endpoint helper (`/api/v1/dashboard/summary`)
- Forwards user/session headers to API
- Retrieves JSON payload for dashboard cards

## Step 2: URI/path building

File: `coyote/services/api_client/endpoints.py`

```python
def dashboard(*parts: Any) -> str:
    return v1("dashboard", *parts)
```

```python
def v1(*parts: Any) -> str:
    normalized = [_normalize(part) for part in parts if part is not None and str(part) != ""]
    return f"/api/v1/{'/'.join(normalized)}"
```

Result for `dashboard("summary")`:

```text
/api/v1/dashboard/summary
```

## Step 3: API router entrypoint

File: `api/routers/dashboard.py`

```python
@router.get("/api/v1/dashboard/summary", response_model=DashboardSummaryPayload)
def dashboard_summary(
    user: ApiUser = Depends(require_access()),
    service: DashboardService = Depends(get_dashboard_service),
):
    return util.common.convert_to_serializable(service.summary_payload(user=user))
```

What this does:

- Enforces authenticated access
- Resolves service dependency from `api/deps/services.py`
- Serializes service result to contract-compatible response

## Step 4: Service orchestration

File: `api/services/dashboard_service.py`

```python
sample_rollup_global = self.repository.get_dashboard_sample_rollup(assays=None)
variant_rollup = self.repository.get_dashboard_variant_counts()
```

```python
payload["dashboard_meta"] = {
    "scope_assays": scope_assays,
    "cache_source": "recomputed",
    "cache_hit": False,
}
```

What this does:

- Orchestrates cross-collection reads
- Returns scope/cache metadata for UI/API consumers

## Step 5: Repository + DB access

File: `api/infra/repositories/dashboard_mongo.py`

```python
def get_dashboard_user_rollup(self) -> dict:
    return dict(store.user_handler.get_dashboard_user_rollup() or {})
```

File: `api/infra/db/users.py`

```python
def get_dashboard_user_rollup(self) -> dict:
    pipeline = [{"$facet": {...}}]
    # aggregate role/profession/active-user stats
```

What this does:

- Repository adapts service calls to DB handlers
- DB handlers run Mongo aggregation pipelines
- Output is normalized back in service/UI

## Step 6: Request metrics and audit events

File: `api/middleware.py`

```python
duration_ms = (time.perf_counter() - start) * 1000.0
runtime_app.logger.info(
    "api_request request_id=%s method=%s path=%s status=%s duration_ms=%.2f user=%s ip=%s",
    request_id,
    request.method,
    path,
    response.status_code,
    duration_ms,
    username,
    request_ip(request),
)
emit_request_event(...)
```

What this does:

- Adds per-request structured timing logs
- Emits request/mutation audit events for observability

## Step 7: Render in UI template

File: `coyote/blueprints/dashboard/views.py`

```python
return render_template(
    "dashboard.html",
    total_samples=total_samples_count,
    analysed_samples=analysed_samples_count,
    variant_stats=variant_stats,
    dashboard_meta=dashboard_meta,
)
```

What this does:

- Binds API payload fields to dashboard cards
- Exposes scope/cache metadata for diagnostics in UI if needed

## End-to-end call chain summary

```text
GET /dashboard/ (Flask)
  -> api_endpoints.dashboard("summary")
  -> GET /api/v1/dashboard/summary (FastAPI)
  -> DashboardService.summary_payload()
  -> MongoDashboardRepository + db handlers
  -> payload + metadata
  -> Flask render_template("dashboard.html")
```

## When you add a new field in this route

1. Extend `DashboardSummaryPayload` contract.
2. Add field computation in `DashboardService.summary_payload`.
3. Add repository/db method if new query is needed.
4. Expose field in Flask template render context.
5. Add tests for contract + service + UI behavior.
