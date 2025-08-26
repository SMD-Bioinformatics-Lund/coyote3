# Environments

Use `.env` to configure runtime. Example keys from `example.env`:

```env
SECRET_KEY='SECRET_KEY_PLACEHOLDER'
COYOTE3_FERNET_KEY='FERNET_KEY'
FLASK_MONGO_HOST='MONGO_HOST'
FLASK_MONGO_PORT='MONGO_PORT'
PORT_NBR='PORT_YOU_WANT_YOUR_APP_TO_BE_RUNIING_ON'
FLASK_DEBUG=0
CACHE_REDIS_URL='redis://redis_coyote3:6379/0'
CACHE_REDIS_HOST='redis_coyote3'
COYOTE3_DB_NAME='coyote3'
SCRIPT_NAME='coyote3'
GENS_URI='GENS_URI'
```

- **MongoDB**: `FLASK_MONGO_HOST`, `FLASK_MONGO_PORT`, `COYOTE3_DB_NAME`
- **Caching**: `CACHE_REDIS_URL` or `CACHE_REDIS_HOST`
- **Security**: `SECRET_KEY`, `COYOTE3_FERNET_KEY`
- **Service URIs**: `GENS_URI`, report paths, etc. (see `config.py`)

Run locally with Docker Compose or `flask run` after installing dependencies from `requirements.txt`.
