# Repository Structure

```
coyote/                # App package
  blueprints/          # Flask blueprints (admin, dna, rna, common, ...)
  db/                  # Mongo handlers (samples, variants, roles, schemas, ...)
  services/            # auth (ldap, decorators, session), audit logs
  templates/           # base layout, error pages
  util/                # utilities, access decorators, report utils
config.py              # app configuration (env-driven)
logging_setup.py       # centralized logging with rotation & retention
run.py, wsgi.py        # entry points for dev/prod
Dockerfile, compose    # containerization
```
