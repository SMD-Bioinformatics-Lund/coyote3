# Developer Setup

## Prereqs
- Python (per `pyproject.toml`) or Docker
- MongoDB; optionally Redis for caching

## Local (Docker)
- `docker-compose up --build`
- App runs behind Gunicorn with config in `gunicorn.conf.py`.

## Local (venv)
```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
export FLASK_APP=coyote
flask run
```

Seed env from `example.env` and create an admin user via Admin UI or a small script using `store.user_handler`.
