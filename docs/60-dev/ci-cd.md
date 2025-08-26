# CI/CD & Deployment

- Build Docker image from `Dockerfile`; push to your registry.
- Run under Gunicorn (`gunicorn.conf.py`) behind a reverse proxy.
- Configure env vars per environment (see `example.env`).
- Persist `logs/` and ensure the app user can write to it.
- Back up MongoDB periodically; validate restores.

Add pipeline gates for tests, linting, and docs build.
