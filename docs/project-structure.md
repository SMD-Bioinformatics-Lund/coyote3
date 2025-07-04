# Project Structure
```markdown
coyote3/
├── coyote/
│ ├── blueprints/
│ │ ├── admin/ # Admin UI: routes, forms, utils, templates
│ │ ├── dna/ # DNA analysis: forms, filters, utils, templates
│ │ ├── rna/ # RNA analysis
│ │ ├── coverage/ # Coverage visualization
│ │ ├── dashboard/ # Landing pages, stats
│ │ ├── login/ # Login/logout flows
│ │ ├── userprofile/ # Account management
│ │ ├── public/ # Public panels & explorers
│ │ └── common/ # Shared templates, helpers
│ ├── db/ # MongoDB access: mongo.py + per-collection modules
│ ├── services/ # Authentication, audit logging
│ ├── util/ # Shared decorators, helpers
│ ├── models/ # Business data models (e.g. user)
│ ├── errors/ # Exceptions and handlers
│ └── extensions/ # Flask extensions initialization
├── config.py
├── run_dev.py / wsgi.py
├── gunicorn.conf.py
├── Dockerfile / docker-compose.yml
└── schemas/ # JSON schema definitions
```
