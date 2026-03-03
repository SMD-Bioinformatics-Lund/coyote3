# Refactor Change Log (March 2026)

This chapter records the boundary and maintainability refactors completed in this cycle.

## Completed changes

1. Report rendering boundary clarified
- Flask handles HTML rendering.
- API handles report persistence and structured payload validation.

2. Model ownership cleanup
- Removed model shim imports and consolidated ownership to `api/domain/models`.

3. Utility ownership cleanup
- Removed duplicated utility wrappers and fallback modules.
- Kept web boundary clean by removing direct `coyote -> api` imports.

4. Workflow contract hardening
- Replaced warn-only contract checks with strict HTTP `400` validation errors.
- Added dedicated workflow contract tests.

5. Legacy auth fallback removal
- Removed legacy Flask-session fallback path from API session decoding.
- API now accepts only API-session token/cookie authentication.

6. File hygiene
- Removed repeated legal header blocks from Python files to improve readability.

## Contributor impact

- New development should follow strict API/Web ownership rules.
- New route logic should be implemented in service/domain layers.
- Web changes should remain UI-focused and use integration clients for backend access.

## Next recommended phase

1. Split oversized modules (`api/routes/admin.py`, `api/routes/dna.py`, `api/utils/common_utility.py`) into feature-scoped units.
2. Add route behavior tests per domain (`dna`, `rna`, `reports`, `admin`, `public`).
3. Add CI quality gates for lint/type/test checks.
