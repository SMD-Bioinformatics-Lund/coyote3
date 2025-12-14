# Architecture – Containers (C4‑2)

```mermaid
C4Container
    title Coyote3 Containers
    Container(web, "Flask App", "Python", "Blueprints, services, handlers")
    ContainerDb(db, "MongoDB", "Document DB", "Samples, variants, roles, configs…")
    Container(cache, "Redis", "Cache", "Flask‑Caching")
    Container(ext, "LDAP", "Directory", "Auth (optional)")

    Rel(web, db, "pymongo via MongoAdapter")
    Rel(web, cache, "Flask‑Caching")
    Rel(web, ext, "ldap3 (via LdapManager)")
```

**Key modules**
- `coyote/__init__.py`: app factory, blueprint registration, context processors
- `coyote/extensions/__init__.py`: shared objects (login_manager, mongo, **store**, ldap_manager, util)
- `coyote/db/mongo.py`: **MongoAdapter** + handler wiring
- `coyote/services/`: auth (decorators, LDAP, user session), audit logs
- `coyote/blueprints/`: `admin`, `dna`, `rna`, `common`, `coverage`, `dashboard`, etc.
