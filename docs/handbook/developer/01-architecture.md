# Architecture Overview

## Stack

- Flask (modular blueprints)
- MongoDB (PyMongo + handler-based data access)
- Flask-Login + LDAP integration
- Jinja2 templates + static assets
- Redis-backed Flask-Caching

## App initialization

Entry in `coyote/__init__.py` via `init_app(...)`:

1. load config class (prod/dev/test)
2. initialize login manager
3. initialize Mongo extension and connectivity check
4. initialize `MongoAdapter` and handler wiring
5. register blueprints
6. initialize LDAP manager
7. initialize utility layer
8. attach request hooks and context processors

## Blueprint modules and URL prefixes

- `/samples` -> home
- `/` -> login
- `/profile` -> user profile
- `/dna` -> DNA
- `/rna` -> RNA
- `/` -> common routes
- `/dashboard` -> dashboard
- `/cov` -> coverage
- `/admin` -> admin
- `/public` -> public
- `/handbook` -> handbook

## Cross-cutting concerns

- RBAC + permission decorators
- sample access decorators
- session refresh per request
- cache-backed dashboard and query patterns
- audit logging decorators
