## Testing Guide

Tests are split by execution concern:

- `tests/api/`: API contracts, route behavior, auth, and backend-only logic.
- `tests/web/`: UI and Flask presentation behavior.
- `tests/contract/`: architecture boundary and cross-layer contract checks.
- `tests/unit/`: isolated lower-level logic.

### Core commands

```bash
/home/ram/.virtualenvs/coyote3/bin/python -m pytest -q tests/api
/home/ram/.virtualenvs/coyote3/bin/python -m pytest -q tests/web
/home/ram/.virtualenvs/coyote3/bin/python -m pytest -q tests/contract
/home/ram/.virtualenvs/coyote3/bin/python -m pytest -q tests/unit
```

### Backend startup assertion

The backend is expected to import from `api.main` and expose `/api/v1/health`.
Structural tests should assert the canonical entrypoint and critical package
layout so the repository does not drift back into ad hoc startup paths.
