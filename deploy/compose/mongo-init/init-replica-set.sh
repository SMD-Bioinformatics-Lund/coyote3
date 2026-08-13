#!/bin/sh
set -eu

if [ -z "${MONGO_ROOT_USERNAME:-}" ] || [ -z "${MONGO_ROOT_PASSWORD:-}" ]; then
  echo "[error] MONGO_ROOT_USERNAME and MONGO_ROOT_PASSWORD are required" >&2
  exit 2
fi

if [ -z "${MONGO_REPLICA_SET_NAME:-}" ] || [ -z "${MONGO_REPLICA_MEMBER_HOST:-}" ]; then
  echo "[error] MONGO_REPLICA_SET_NAME and MONGO_REPLICA_MEMBER_HOST are required" >&2
  exit 2
fi

run_mongosh() {
  mongosh \
    --host "${MONGO_SERVICE_HOST:-coyote3_mongo}" \
    --username "$MONGO_ROOT_USERNAME" \
    --password "$MONGO_ROOT_PASSWORD" \
    --authenticationDatabase admin \
    --quiet "$@"
}

until run_mongosh --eval 'db.adminCommand({ping: 1}).ok' >/dev/null 2>&1; do
  echo "[info] waiting for MongoDB root authentication"
  sleep 2
done

export MONGO_REPLICA_SET_NAME MONGO_REPLICA_MEMBER_HOST
run_mongosh --eval '
const status = (() => {
  try { return rs.status(); } catch (error) { return { code: error.code }; }
})();
if (status.code === 94) {
  rs.initiate({ _id: process.env.MONGO_REPLICA_SET_NAME, members: [{ _id: 0, host: process.env.MONGO_REPLICA_MEMBER_HOST }] });
  print(`[mongo-init] initiated replica set ${process.env.MONGO_REPLICA_SET_NAME}`);
} else {
  print(`[mongo-init] replica set ${process.env.MONGO_REPLICA_SET_NAME} is already configured`);
}
'

until run_mongosh --eval 'db.hello().isWritablePrimary' | grep -q true; do
  echo "[info] waiting for the replica-set primary"
  sleep 2
done

echo "[ok] replica set is writable"
