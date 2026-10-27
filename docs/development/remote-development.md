# Remote development deployment

Use compiled images when browsing the development environment from another
machine. Nginx serves bundled frontend assets with compression and long-lived
caching for content-hashed files. HTML is revalidated so new deployments load
the current asset names. The environment file still selects development branding,
database connections, storage, and public URL.

For a development stack using modern Compose, build and replace only the
frontend with the base file. Keep the existing environment and project identity:

```bash
bash scripts/deployment/compose-with-version.sh -p coyote3-dev --env-file .coyote3_dev_env \
  -f deploy/compose/docker-compose.yml build frontend
bash scripts/deployment/compose-with-version.sh -p coyote3-dev --env-file .coyote3_dev_env \
  -f deploy/compose/docker-compose.yml up -d --no-deps --no-build frontend
```

This targeted command leaves API reload and other running services as they are.
Repeat it after frontend edits. `ENV_NAME=development` in the selected env file
makes the wrapper select `-dev` application image tags. No additional overlay is
needed for image naming. Do not include the development overlay in this build:
it deliberately removes the frontend build and runs the Node/Vite image instead.

For a complete compiled dev stack, use the same files with `up -d --build`
instead of the service-specific commands. This also removes API reload/source
mounts; backend changes then require rebuilding their images. All application
images retain the `-dev` tag. MongoDB remains independently deployed.

To return the frontend to live editing, use the same base plus development overlay:

```bash
bash scripts/deployment/compose-with-version.sh -p coyote3-dev --env-file .coyote3_dev_env \
  -f deploy/compose/docker-compose.yml \
  -f deploy/compose/docker-compose.dev.yml up -d --no-deps frontend
```

Keep any center storage overlays after these files in their recorded order.
Older Docker/Compose installations use the matching definitions under
`deploy/legacy/` instead; do not mix modern `!reset` overlays into that file set.
The first-center installer requires the modern `docker compose` plugin. See the
[container reference](../deployment/containers-and-reverse-proxy.md) for the
separately supported older-container definitions.

Do not use `down`, volume removal, or Docker prune for this switch.
