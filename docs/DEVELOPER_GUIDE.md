# Coyote3 Developer Guide

## Audience
This guide is for engineers contributing to Coyote3 backend, UI, and platform automation.

## Scope
This manual explains repository structure, local setup, runtime model, coding boundaries, testing workflow, and safe extension patterns for API routes, contracts, workflows, UI pages, and policy features.

## Key Concepts
For shared terminology, see [GLOSSARY.md](GLOSSARY.md).

## Related Documents
- Architecture: [ARCHITECTURE_OVERVIEW.md](ARCHITECTURE_OVERVIEW.md)
- API contracts and endpoint behavior: [API_REFERENCE.md](API_REFERENCE.md)
- Security and RBAC: [SECURITY_MODEL.md](SECURITY_MODEL.md)
- Data model: [DATA_MODEL.md](DATA_MODEL.md)
- Testing policy: [TESTING_STRATEGY.md](TESTING_STRATEGY.md)
- Extension procedures: [EXTENSION_PLAYBOOK.md](EXTENSION_PLAYBOOK.md)
- Deployment: [DEPLOYMENT_AND_OPERATIONS.md](DEPLOYMENT_AND_OPERATIONS.md)

---

## 1. Repository Layout

```text
coyote3/
├── api/
│   ├── app.py
│   ├── routes/
│   ├── contracts/
│   ├── core/
│   ├── security/
│   ├── audit/
│   ├── infra/
│   │   ├── db/
│   │   └── external/
│   ├── domain/
│   ├── errors/
│   ├── settings.py
│   └── extensions.py
├── coyote/
│   ├── __init__.py
│   ├── blueprints/
│   ├── templates/
│   ├── static/
│   ├── services/
│   │   └── api_client/
│   └── util/
├── tests/
│   ├── unit/
│   ├── api/
│   ├── web/
│   └── contract/
├── docs/
├── deploy/
├── config/
├── scripts/
├── pyproject.toml
├── .pre-commit-config.yaml
└── mkdocs.yml
```

### Ownership summary
- `api/`: authoritative backend logic, security, audit, and persistence.
- `coyote/`: server-rendered UI and API consumption layer.
- `tests/`: quality gates by scope.
- `docs/`: architecture, operations, and user/developer manuals.

---

## 2. Architectural Boundaries for Contributors

### 2.1 API ownership
Use API modules when adding:
- business rules
- workflow orchestration
- data mutation logic
- permission enforcement
- audit event emission
- MongoDB read/write behavior

### 2.2 UI ownership
Use UI modules when adding:
- page routing and template composition
- user input mapping to API request payloads
- rendering and interaction behavior

### 2.3 Forbidden coupling
Do not:
- import `api/*` internals from `coyote/*`
- use Mongo drivers in UI modules
- duplicate backend workflow logic in Flask blueprints

Boundary tests enforce these rules:
- `tests/contract/test_ui_forbidden_backend_imports.py`
- `tests/contract/test_ui_forbidden_mongo_usage.py`

---

## 3. Local Development Setup

## 3.1 Prerequisites
- Python 3.12
- Node.js/NPM (for CSS build/watch)
- Docker + Docker Compose

## 3.2 Python environment
```bash
python3 -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
```

## 3.3 Frontend assets
```bash
npm install
npm run build:css
```

## 3.4 Environment files
Use `.env` and local environment files according to deployment docs. Ensure API and UI share compatible base URL/session settings.

---

## 4. Running the System Locally

## 4.1 API runtime only
```bash
.venv/bin/python run_api.py
```

## 4.2 UI runtime only
```bash
.venv/bin/python run.py
```

## 4.3 Docker development stack
```bash
docker compose -f deploy/compose/docker-compose.dev.yml up --build
```

Expected topology:
- UI service
- API service
- Mongo service
- optional Redis/Tailwind watcher based on compose profile

---

## 5. Test Execution Model

### 5.1 Marker-based suites
```bash
.venv/bin/pytest -q -m unit
.venv/bin/pytest -q -m api
.venv/bin/pytest -q -m web
.venv/bin/pytest -q -m contract
```

### 5.2 Common targeted runs
```bash
.venv/bin/pytest -q tests/api/routes
.venv/bin/pytest -q tests/web
.venv/bin/pytest -q tests/contract
```

### 5.3 Lint and formatting
```bash
.venv/bin/ruff format .
.venv/bin/ruff check .
```

---

## 6. Adding a New FastAPI Endpoint

## 6.1 Workflow
1. Define request/response models in `api/contracts/`.
2. Add route in the correct `api/routes/*.py` module.
3. Implement logic in `api/core/*`.
4. Add or extend persistence methods in `api/infra/db/*`.
5. Add access dependency checks (`require_access`) as needed.
6. Emit audit events for governed operations.
7. Add tests in `tests/api/` and `tests/unit/`.
8. Update API docs.

## 6.2 Example pattern
```python
# api/contracts/example.py
from pydantic import BaseModel

class SampleSummaryResponse(BaseModel):
    sample_id: str
    assay_group: str

# api/routes/samples.py
from fastapi import Depends
from api.app import app, require_access
from api.contracts.example import SampleSummaryResponse
from api.core.samples.summary import get_sample_summary

@app.get("/api/v1/samples/{sample_id}/summary", response_model=SampleSummaryResponse)
def sample_summary(sample_id: str, user=Depends(require_access(permissions=["view_sample"]))):
    return get_sample_summary(sample_id=sample_id, user=user)
```

---

## 7. Adding a New UI Page or Blueprint Route

## 7.1 Workflow
1. Identify existing blueprint or create a coherent new one under `coyote/blueprints/`.
2. Add route handler that remains thin.
3. Call API via `coyote/services/api_client/*` helper.
4. Render template with mapped context.
5. Add web tests and contract-safe checks.
6. Update user/developer docs.

## 7.2 Blueprint route pattern
```python
# coyote/blueprints/example/views.py
from flask import render_template
from flask_login import login_required
from coyote.blueprints.example import example_bp
from coyote.services.api_client import get_web_api_client, forward_headers

@example_bp.route("/cases/<string:sample_id>")
@login_required
def case_view(sample_id: str):
    payload = get_web_api_client().get_json(
        f"/api/v1/samples/{sample_id}/summary",
        headers=forward_headers(),
    )
    return render_template("case_view.html", data=payload)
```

---

## 8. Adding New Permissions and Roles

## 8.1 Permission addition flow
1. Define permission metadata in governed configuration collections/workflows.
2. Ensure route dependencies enforce the permission where required.
3. Update admin UI exposure if needed.
4. Add tests for allow/deny behavior.

## 8.2 Role addition flow
1. Define role document and access level policy.
2. Map permissions to role.
3. Verify effective access in API route tests.
4. Validate UI visibility behavior from policy outcomes.

---

## 9. Adding Audit Events

1. Identify operation requiring traceability.
2. Emit backend event from API workflow path.
3. Include actor, action, entity, and timestamp context.
4. Add tests verifying event emission semantics.

Do not write authoritative audit events from UI code.

---

## 10. Adding New Assay Groups

1. Extend configuration and metadata sources used by API/UI.
2. Ensure API workflows support assay-specific behavior.
3. Verify sample filtering and variant/rna pages handle new group.
4. Add regression tests for list/detail/report paths.
5. Update UI guide and glossary if user-visible terminology changes.

---

## 11. Error Handling and Logging

### 11.1 API errors
- Use typed exceptions and route-level normalization.
- Return stable error envelopes for client handling.

### 11.2 UI errors
- Wrap API failures using UI error handlers and user-safe messaging.
- Keep detailed diagnostics in logs.

### 11.3 Logging conventions
- Include route/module context in messages.
- Do not log secrets or sensitive credentials.
- Use backend logs for policy/audit-sensitive tracing.

---

## 12. Naming and Module Conventions

- Route modules: noun-family names (`samples.py`, `reports.py`).
- Contract modules: route/domain-aligned names (`samples.py`, `dna.py`).
- Core modules: workflow/domain intent (`workflows/filter_normalization.py`).
- UI blueprint modules: view purpose grouping (`views_samples.py`, `views_reports.py`).
- Keep names descriptive and stable; avoid generic `helpers.py` growth without domain prefix.

---

## 13. Common Contributor Mistakes to Avoid

1. Adding business logic to Flask view handlers.
2. Returning ad-hoc dictionaries from API routes without contract models.
3. Querying Mongo directly from route modules instead of infra handlers.
4. Skipping permission tests for new mutating endpoints.
5. Updating UI behavior without corresponding docs updates.

---

## 14. CI/CD Expectations

A contribution is expected to satisfy:
- formatting and lint checks
- relevant test suites (`unit`, `api`, `web`, `contract`)
- documentation updates for behavior/structure changes
- clear commit messages and review-ready scope boundaries

GitHub workflow quality checks should match local commands documented in this guide.

---

## 15. Fast Onboarding Checklist

- [ ] Set up `.venv` and install dependencies
- [ ] Build frontend assets
- [ ] Run API and UI locally
- [ ] Execute marker test suites
- [ ] Read architecture and security docs
- [ ] Implement first change with route->core->infra pattern
- [ ] Update docs before opening PR
