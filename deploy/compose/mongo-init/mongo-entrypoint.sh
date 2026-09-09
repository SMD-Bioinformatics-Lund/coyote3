#!/bin/sh
set -eu

# Prepare files as root, then run the official entrypoint with the configured IDs.
for value in "${MONGO_UID:-}" "${MONGO_GID:-}"; do
  case "$value" in
    ''|*[!0-9]*)
      echo '[error] MONGO_UID and MONGO_GID must be positive numeric IDs' >&2
      exit 1 ;;
  esac
  if [ "$value" -eq 0 ]; then
    echo '[error] MongoDB must run with non-root UID/GID' >&2
    exit 1
  fi
done
source_key=/etc/mongo-keyfile/keyfile
runtime_key=/run/coyote3-mongo/keyfile
if [ ! -f "$source_key" ] || [ ! -s "$source_key" ] || [ ! -r "$source_key" ]; then
  echo '[error] Mongo keyfile must be a readable, nonempty regular file' >&2
  exit 1
fi
umask 077
mkdir -p /run/coyote3-mongo
cp "$source_key" "$runtime_key"
chown "$MONGO_UID:$MONGO_GID" /run/coyote3-mongo "$runtime_key"
chmod 700 /run/coyote3-mongo
chmod 400 "$runtime_key"
mkdir -p /data/db /data/configdb
find /data/db /data/configdb -xdev \
  \( ! -uid "$MONGO_UID" -o ! -gid "$MONGO_GID" \) \
  -exec chown -h "$MONGO_UID:$MONGO_GID" {} +
export HOME=/tmp
exec gosu "$MONGO_UID:$MONGO_GID" /usr/local/bin/docker-entrypoint.sh "$@"
