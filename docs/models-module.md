# Models Module (`coyote/models/`)

This module defines business-level data models that represent application entities, provide validation, and encapsulate domain logic. Unlike the lower-level database handlers, models focus on structure, rules, and behavior.

---

## Purpose of Models

- Add validation and behavior on top of raw data
- Map data from DB to domain objects
- Encapsulate permissions, roles, and user-related workflows
- Complement database access layer (`db/`) with logic-rich classes

---

## `user.py`

### Overview

The `User` class represents an application user and supports:

- Attribute validation (e.g., username format, email correctness)
- Role and permission handling
- Session integration via methods like `is_authenticated`
- Business logic such as password hashing or checking access

### Sketch of Class Definition

```python
class User:
    def __init__(self, data: dict):
        self.username = data.get("username")
        self.email = data.get("email")
        self.roles = data.get("roles", [])
        # Possibly more attributes: full_name, permissions, etc.

    def is_authenticated(self) -> bool:
        ...

    def has_role(self, role_name: str) -> bool:
        ...

    def has_permission(self, perm_name: str) -> bool:
        ...

    @classmethod
    def from_identity(cls, user_id: str) -> "User":
        # Load data from DB via store.user_handler.get(...)
        # Return User instance
```

## Interaction with Services
- `user_session.py` in `services/auth` constructs `User` objects on login
- Flask-Login uses `User` methods (`is_authenticated`, `is_active`) for session control
- Access control decorators check `User.has_role()` and `User.has_permission()`

## Extending the Models Module
To add a domain model:
- Create a new file, e.g., `coyote/models/myentity.py`
- Define a class with relevant attributes and methods
- Use in blueprint or service to shape business logic

```python
class MyEntity:
    def __init__(self, data: dict):
        self.name = data["name"]
        self.value = data["value"]

    def is_valid(self) -> bool:
        return isinstance(self.value, (int, float)) and self.value > 0

```

## Integration with Handlers and Blueprints
When you're handling an entity:

1. Retrieve raw data via DB layer
```python
doc = store.sample_handler.get_by_id(sample_id)
```

2. Wrap in model class
```python
sample = Sample(doc)
```

3. Use model methods to drive logic or formatting in view/template

```python
if not sample.is_valid_metadata():
    flash("Incomplete sample metadata", ...)
```

This separation keeps views/controllers light and models expressive.