# Services Module (`coyote/services/`)

This module implements core services that are shared across blueprints, including authentication and audit logging. Services encapsulate crucial cross-cutting concerns like session management, access control, and activity tracking.

---

## Authentication Services (`services/auth`)

### 1. `user_session.py`

- Manages user login, logout, and session state.
- Integrates with Flask-Login to establish `current_user`.
- Typical methods:
  - `login_user(user, remember)`
  - `logout_user()`
  - `load_user(user_id) -> User`

### 2. `ldap.py`

- Provides optional LDAP authentication integration.
- Connects to enterprise directory for credential validation.
- Used when the login method for the user is set to `LDAP`.

### 3. `decorators.py`

Offers reusable route protection:

```python
from functools import wraps

def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not current_user.is_authenticated:
            return redirect(login_url)
        return f(*args, **kwargs)
    return decorated
```

- Also includes decorators like @requires_role(...) and @requires_permission(...).
- Best practices: use @wraps to preserve function metadata
- Avoid complex logic in decorators; keep them simple and reusable.
- Example usage:

```python
@app.route('/admin')
@requires_role('admin')
def admin_dashboard():
    ...
```

## Audit Logging Services (services/audit_logs)
Implements change tracking for sensitive operations.

1. `logger.py`
- Defines a centralized audit logger, writing structured logs (JSON or plain text).
- Records user, timestamp, request path, and operation.

2. `decorators.py`
- Contains `@log_action(action="update")` decorator.
- Wraps CRUD handlers to automatically log before/after state.

### Example:
```python
@log_action(action="delete_variant")
def delete_variant(variant_id):
    ...
```
- Inspired by standard audit patterns used in Flask logging middleware

## Integration
Services are initialized and registered in application factory, enabling:
- `@login_required` on blueprint routes
- `@log_action` usage in data handlers/controllers

## Extending Services
Adding Custom Decorators
```python
def requires_permission(perm):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if not current_user.has_permission(perm):
            abort(403)
        return f(*args, **kwargs)
    return wrapper

```

Logging New Action
```python
@log_action(action="export_report")
def export_report(sample_id):
    ...

```

