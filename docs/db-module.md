# Database Layer (`coyote/db/`)

This module handles low-level MongoDB interaction using PyMongo, structured via a `MongoAdapter` and modular Handler classes.

---

## `mongo.py` – MongoAdapter

**Purpose**  
Initializes database connections and exposes named collections and handlers.

### Key Responsibilities

- Establish MongoDB client via connection URI (`MONGO_URI`)
- Set up databases (`MONGO_DB_NAME`, `BAM_SERVICE_DB_NAME`) as `self.coyote_db` and `self.bam_db`
- Create attributes for each MongoDB collection using `DB_COLLECTIONS_CONFIG` mapping
- Instantiate handler classes (e.g., `VariantsHandler`, `FusionsHandler`, `UsersHandler`) as:

```python
self.variant_handler = VariantsHandler(self)
self.fusion_handler = FusionsHandler(self)
...
```
## How it works
```python
mongo = MongoAdapter()
mongo.init_from_app(app)  # Using Flask app’s config
# Available handlers:
mongo.variant_handler.get_sample_variants(sample_id="123")
mongo.user_handler.create_user({...})
```
This centralizes all DB access and ensures consistent usage across the app.

## `base.py` – BaseHandler
Base handler class providing common methods and pattern for all data handlers.
```python
class BaseHandler:
    def __init__(self, adapter):
        self.adapter = adapter
        self.current_user = current_user  # from flask_login
        self.app = current_app

        self.handler_collection = None

    def set_collection(self, collection):
        """Bind a PyMongo Collection to this handler."""

    def get_collection(self):
        """Return collection or raise NotImplementedError."""
````

## Typical Usage
```python
class ExampleHandler(BaseHandler):
    def __init__(self, adapter):
        super().__init__(adapter)
        self.set_collection(adapter.example_collection)

    def get_sample_fusions(self, query: dict):
        return self.get_collection().find(query)
```

This pattern enforces:
- Safe MongoDB collection binding
- Future-proofing for shared methods (e.g., audit, hide, update)
  
  
## Extending the Database Layer

### Add a new handler
1. Create coyote/db/myentity.py:
```python
from coyote.db.base import BaseHandler

class MyEntityHandler(BaseHandler):
    def __init__(self, adapter):
        super().__init__(adapter)
        self.set_collection(adapter.myentity_collection)

    def find_by_field(self, value):
        return self.handler_collection.find({"field": value})
```

2. Register collection in DB_COLLECTIONS_CONFIG in config.py:
```python
DB_COLLECTIONS_CONFIG:
  myapp_db:
    myentity_collection: "my_entity"
```

3. In mongo.py, import and initialize:
```python
from coyote.db.myentity import MyEntityHandler

class MongoAdapter:
    ...
    def _setup_handlers(self):
        self.myentity_handler = MyEntityHandler(self)
```

4. Use in app:
```python
from coyote.db.mongo import store  # Initialized in extensions
items = store.myentity_handler.find_by_field("x")
```  

##  Integration with Flask
- Initialized via: `mongo_adapter.init_from_app(app)` in extensions/.
- Shared globally: `store = MongoAdapter()` and imported when needed.
- Component access: Use `store.<xxx>_handler` from any blueprint or service for CRUD operations.

## Benefits
- Centralized connection pooling and client reuse
- Clear separation of domain-specific logic
- Easy extension: new handlers, collections
- Consistent API and error handling pattern

## Summary Table
| Component        | Location        | Responsibilities                                                           |
|------------------|------------------|-----------------------------------------------------------------------------|
| `MongoAdapter`   | `db/mongo.py`    | Initializes MongoDB client, sets up databases and collections, instantiates all Handler classes |
| `BaseHandler`    | `db/base.py`     | Provides foundation for MongoDB handlers: collection binding, shared behavior |
| Domain Handlers  | `db/*.py`        | Manage collection-specific operations (e.g. `VariantsHandler`, `FusionsHandler`, `UsersHandler`, etc.) |
