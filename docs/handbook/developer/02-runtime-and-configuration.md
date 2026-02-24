# Runtime and Configuration

## Config classes

Defined in `config.py`:

- `ProductionConfig`
- `DevelopmentConfig`
- `TestConfig`

Each inherits from `DefaultConfig` and overrides runtime-specific fields.

## Critical config values

- app identity/version fields
- Mongo host/port/db
- DB collection mapping TOML file path
- LDAP settings
- cache backend and Redis URL
- report base path
- session cookie name
- secret keys and Fernet key

## Collection mapping strategy

`DB_COLLECTIONS_CONFIG` loads TOML mapping and validates that:

- selected `MONGO_DB_NAME` exists
- selected `BAM_SERVICE_DB_NAME` exists

If missing, startup raises error early.

## Environment files in repo

- `.env`
- `.coyote3_env`
- `.coyote3_dev_env`
- `example.env`

## Run entries

- `wsgi.py` (main runtime)
- `run.py`, `run_dev.py` (alternate run modes)
- compose files and install scripts for containerized runs
