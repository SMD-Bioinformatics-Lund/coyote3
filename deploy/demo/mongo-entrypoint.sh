#!/bin/sh
set -eu
umask 077
mkdir -p /run/coyote-demo
printf '%s' "${COYOTE_DEMO_MONGO_KEY:?Generated demo replica key is required}" > /run/coyote-demo/keyfile
chown mongodb:mongodb /run/coyote-demo /run/coyote-demo/keyfile
chmod 400 /run/coyote-demo/keyfile
exec /usr/local/bin/docker-entrypoint.sh "$@"
