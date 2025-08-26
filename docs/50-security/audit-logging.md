# Audit Logging

- Use `@log_action(action_name=..., call_type=...)` to automatically capture:
  - user, IP, route, method, timestamp, status
  - custom metadata (e.g., `sample_id`, `assay_id`) from `flask.g`
- Admin UI: **Audit** page for search and review.

Code: `coyote/services/audit_logs/logger.py`, `.../decorators.py`.
