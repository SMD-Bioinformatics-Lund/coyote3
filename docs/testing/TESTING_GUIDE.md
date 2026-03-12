## Testing Guide

Tests are split by execution concern:

- `tests/api/`: API contracts, route behavior, auth, and backend-only logic.
- `tests/ui/`: UI and Flask presentation behavior.
- `tests/integration/`: architecture boundary and cross-layer integration checks.
- `tests/unit/`: isolated lower-level logic.

### Core commands

```bash
/home/ram/.virtualenvs/coyote3/bin/python -m pytest -q tests/api
/home/ram/.virtualenvs/coyote3/bin/python -m pytest -q tests/ui
/home/ram/.virtualenvs/coyote3/bin/python -m pytest -q tests/integration
/home/ram/.virtualenvs/coyote3/bin/python -m pytest -q tests/unit
```

### Backend startup assertion

The backend is expected to import from `api.main` and expose `/api/v1/health`.
Structural tests should assert the canonical entrypoint and critical package
layout so the repository does not drift back into ad hoc startup paths.
