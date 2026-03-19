# UI URL To Backend Process Flow

This guide shows what happens when a user hits a URL in the UI, how Flask calls the API, and how the API resolves data and response payloads.

The examples use real routes in this repository.

## 1. Common Request Path (All Flows)

1. Browser requests a Flask URL in `coyote/blueprints/*`.
2. Flask view uses endpoint builders in `coyote/services/api_client/endpoints.py`.
3. Flask view calls API through `get_web_api_client()` and `forward_headers()`.
4. API route in `api/routers/*` validates access and input, then delegates to service/core code.
5. Service/repository reads or mutates Mongo and returns contract-shaped data.
6. Flask renders template, redirects, or returns file response to browser.

Key files:
- `coyote/services/api_client/api_client.py`
- `coyote/services/api_client/endpoints.py`
- `api/routers/*`
- `api/contracts/*`

---

## 2. Flow A: Page Render (GET -> HTML)

Example URL:
- UI URL: `/dna/sample/<sample_id>`
- Flask handler: `list_dna_findings` in `coyote/blueprints/dna/views_dna_findings.py`

How it maps to API:
1. Flask builds endpoint with `api_endpoints.dna_sample(sample_id, "small_variants")`.
2. Builder resolves to `/api/v1/samples/{sample_id}/small-variants`.
3. Flask calls API `GET` and receives JSON payload.
4. API route `list_dna_variants` in `api/routers/small_variants.py` returns `DnaVariantsListPayload`.
5. Flask renders `list_dna_findings.html` with that payload.

Process flow:
```text
Browser GET /dna/sample/69...
 -> Flask dna_bp.list_dna_findings
 -> API GET /api/v1/samples/69.../small-variants
 -> FastAPI small_variants.list_dna_variants
 -> DnaService.list_variants_payload
 -> Mongo handlers (samples/variants/cnvs/annotations/...)
 -> JSON payload
 -> Flask render_template("list_dna_findings.html", ...)
 -> HTML response
```

---

## 3. Flow B: In-Page Mutation (POST -> API PUT/DELETE -> HTML refresh)

Example action:
- User submits filter form on DNA findings page.

How it maps:
1. Browser `POST /dna/sample/{sample_id}`.
2. Flask handler `list_dna_findings` inspects form.
3. Flask calls:
   - `PUT /api/v1/samples/{sample_id}/filters` (update), or
   - `DELETE /api/v1/samples/{sample_id}/filters` (reset).
4. Flask then re-fetches `GET /api/v1/samples/{sample_id}/small-variants`.
5. Page is rendered with updated filter state and result rows.

Process flow:
```text
Browser POST /dna/sample/69...
 -> Flask parses form
 -> API PUT/DELETE /api/v1/samples/69.../filters
 -> API samples router -> service -> sample handler update
 -> Flask API re-fetch (GET small-variants)
 -> render_template with updated data
```

---

## 4. Flow C: API-Generated File Download (CSV content via API)

Example URL:
- UI URL: `/dna/sample/{sample_id}/exports/snvs.csv`
- Flask handler: `download_snv_csv` in `views_dna_findings.py`

How it maps:
1. Flask calls `GET /api/v1/samples/{sample_id}/small-variants/exports/snvs/context`.
2. API route `export_snv_csv_context` builds filtered rows and CSV text.
3. API returns JSON `{filename, content, row_count}`.
4. Flask wraps `content` into `send_file(...)` and returns downloadable CSV response.

Process flow:
```text
Browser GET /dna/sample/69.../exports/snvs.csv
 -> Flask download_snv_csv
 -> API GET /api/v1/samples/69.../small-variants/exports/snvs/context
 -> DnaService.build_snv_export_rows + export_rows_to_csv
 -> API JSON (filename + csv content)
 -> Flask send_file(BytesIO(csv))
 -> Browser download
```

---

## 5. Flow D: Report Preview/Save (two-step API flow + API-built report path)

Example URLs:
- Preview: `/dna/sample/{sample_id}/preview_report`
- Save: `/dna/sample/{sample_id}/report/save`
- Flask handlers: `generate_dna_report`, `save_dna_report` in `coyote/blueprints/dna/views_reports.py`

Preview path:
1. Flask calls API helper `fetch_preview_payload("dna", sample_id, ...)`.
2. Endpoint builder maps DNA reports to:
   - `GET /api/v1/samples/{sample_id}/reports/dna/preview`
3. API route `preview_report` in `api/routers/reports.py` builds template context.
4. Flask renders returned template/context to HTML preview.

Save path:
1. Flask fetches preview payload with snapshot rows.
2. Flask renders HTML.
3. Flask sends `POST /api/v1/samples/{sample_id}/reports/dna` with `{html, snapshot_rows}`.
4. API computes report id/path/file and persists:
   - report location built in `api/core/reporting/report_paths.py`
   - write file + save report metadata + snapshot rows

Report path contract:
- API requires `assay_config.reporting.report_path`.
- `report_path` is joined with `REPORTS_BASE_PATH` to create the output directory.

Process flow:
```text
Browser GET /dna/sample/69.../preview_report
 -> Flask generate_dna_report
 -> API GET /api/v1/samples/69.../reports/dna/preview
 -> API builds report context
 -> Flask render template html

Browser GET /dna/sample/69.../report/save
 -> Flask save_dna_report
 -> API GET preview (include snapshot)
 -> Flask render html
 -> API POST /api/v1/samples/69.../reports/dna {html, snapshot_rows}
 -> API build report_id/report_path/report_file and persist
 -> Flask redirect + flash success
```

---

## 6. Flow E: Existing Report File Open/Download (path resolution + disk read in UI)

Example URLs:
- View: `/samples/{sample_id}/reports/{report_id}`
- Download: `/samples/{sample_id}/reports/{report_id}/download`
- Flask handlers: `view_report`, `download_report` in `coyote/blueprints/home/views_reports.py`

How it maps:
1. Flask calls API for report context (`.../reports/{report_id}/context`) to get resolved filepath.
2. Flask validates file exists on disk.
3. Flask returns `send_file(...)` either inline or attachment.

Notes:
- API is source of truth for report metadata.
- UI does the final disk streaming response to browser.
