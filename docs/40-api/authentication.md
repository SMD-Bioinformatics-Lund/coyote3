# Authentication & Sessions

- **Flask‑Login** session with user wrapper from `services/auth/user_session.py`.
- Optional **LDAP** via `services/auth/ldap.py`; otherwise local auth.
- Protect routes with:
  - `@require("permission", min_role="...", min_level=N)`
  - `@require_sample_access("sample_id")` for assay‑scoped access
  - `@admin_required` for high‑risk actions
- CSRF enabled via Flask‑WTF (see `config.py`).

Tokens/REST externalization is not enabled by default; the app serves a server‑rendered UI.
