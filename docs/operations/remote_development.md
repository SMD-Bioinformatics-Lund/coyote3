# Remote development deployment

Use compiled images when browsing the development environment from another
machine. Nginx serves bundled frontend assets with compression and long-lived
caching for content-hashed files. HTML is revalidated so new deployments load
the current asset names. The environment file still selects development branding,
database connections, storage, and public URL.

For legacy Docker, build and replace only the frontend of an existing dev stack:

```bash
bash scripts/compose-with-version.sh -p coyote3-dev --env-file .coyote3_dev_env \
  -f deploy/legacy/docker-compose.yml \
  -f deploy/legacy/docker-compose.remote-dev.yml build frontend
bash scripts/compose-with-version.sh -p coyote3-dev --env-file .coyote3_dev_env \
  -f deploy/legacy/docker-compose.yml \
  -f deploy/legacy/docker-compose.remote-dev.yml up -d --no-deps frontend
```

This targeted command leaves API reload and other running services as they are.
Repeat it after frontend edits. Do not combine the remote-dev overlay with the
Vite `docker-compose.dev.yml` definition.

For a complete compiled dev stack, use the same files with `up -d --build`
instead of the service-specific commands. This also removes API reload/source
mounts; backend changes then require rebuilding their images. All application
images retain the `-dev` tag. MongoDB remains independently deployed.

With modern Compose, use the corresponding two files under `deploy/compose/`.
To return to live editing, use the legacy standalone `docker-compose.dev.yml`,
or the modern base plus `docker-compose.dev.yml`, and recreate the frontend.

Do not use `down`, volume removal, or Docker prune for this switch.
