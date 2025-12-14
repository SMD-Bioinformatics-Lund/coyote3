# Configuration Reference

Coyote3 is configured primarily via environment variables read in `config.py`.

## Security
- `SECRET_KEY`: Flask sessions & CSRF
- `COYOTE3_FERNET_KEY`: symmetric encryption for versioned payloads & secrets
- `WTF_CSRF_ENABLED`: CSRF protection

## Databases
- `FLASK_MONGO_HOST`, `FLASK_MONGO_PORT`, `COYOTE3_DB_NAME`: primary DB
- `BAM_SERVICE_DB_NAME`: auxiliary BAM service DB (if used)

## Caching
- `CACHE_REDIS_URL` or `CACHE_REDIS_HOST`: Redis connection for Flask‑Caching

## Services
- `GENS_URI`: external service for gene info
- LDAP: see `services/auth/ldap.py` for `LDAP_*` options

Consult `config.py` for defaults and the full list. Some collection mappings are loaded from a TOML file referenced by `_PATH_DB_COLLECTIONS_CONFIG`.
