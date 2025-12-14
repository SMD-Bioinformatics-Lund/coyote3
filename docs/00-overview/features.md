# Features

- **Samples dashboard & viewers** for DNA (variants, CNVs, translocations, biomarkers) and RNA (fusions).
- **Dynamic assay panels (ASP)** and **assay configurations (ASPC)** driven by schemas in MongoDB.
- **In‑silico gene lists (ISGL)** per assay with versioning and print‑friendly views.
- **Role/Permission management**: create roles, attach permissions, set access levels.
- **Audit logs**: searchable admin page (`/admin/audit`) powered by decorators in `services/audit_logs`.
- **Configurable reports**: print layouts in `admin/templates/*/print_*.html` and `print_layout.html`.
- **Caching** with Flask‑Caching; **Redis** backend supported.
- **LDAP auth (optional)** via `services/auth/ldap.py` with app fallbacks.
- **Structured logging** with rotation & retention (`logging_setup.py`).

> See `coyote/blueprints/admin/templates/` for concrete admin features: users, roles, permissions, schemas, ASP/ASPC, ISGL, audit.
