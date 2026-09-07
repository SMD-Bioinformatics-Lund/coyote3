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
    "mongodb://${MONGO_SERVICE_HOST:-mongo}:27017/admin?directConnection=true" \
    --username "$MONGO_ROOT_USERNAME" \
    --password "$MONGO_ROOT_PASSWORD" \
    --authenticationDatabase admin \
    --quiet "$@"
}

attempt=1
max_attempts="${MONGO_INIT_MAX_ATTEMPTS:-60}"
until run_mongosh --eval 'db.adminCommand({ping: 1}).ok' >/dev/null 2>&1; do
  if [ "$attempt" -ge "$max_attempts" ]; then
    echo "[error] MongoDB did not accept root authentication after ${max_attempts} attempts" >&2
    run_mongosh --eval 'db.adminCommand({ping: 1})'
    exit 1
  fi
  echo "[info] waiting for MongoDB root authentication"
  attempt=$((attempt + 1))
  sleep 2
done

export MONGO_REPLICA_SET_NAME MONGO_REPLICA_MEMBER_HOST
run_mongosh --eval '
const config = db.getSiblingDB("local").getCollection("system.replset").findOne();
if (config === null) {
  rs.initiate({ _id: process.env.MONGO_REPLICA_SET_NAME, members: [{ _id: 0, host: process.env.MONGO_REPLICA_MEMBER_HOST }] });
  print(`[mongo-init] initiated replica set ${process.env.MONGO_REPLICA_SET_NAME}`);
} else {
  if (config._id !== process.env.MONGO_REPLICA_SET_NAME) {
    throw new Error(`MongoDB is configured for replica set ${config._id}, expected ${process.env.MONGO_REPLICA_SET_NAME}`);
  }
  print(`[mongo-init] replica set ${process.env.MONGO_REPLICA_SET_NAME} is already configured`);
}
'

attempt=1
until run_mongosh --eval 'db.hello().isWritablePrimary' | grep -q true; do
  if [ "$attempt" -ge "$max_attempts" ]; then
    echo "[error] replica set did not elect a writable primary after ${max_attempts} attempts" >&2
    run_mongosh --eval 'db.hello()'
    exit 1
  fi
  echo "[info] waiting for the replica-set primary"
  attempt=$((attempt + 1))
  sleep 2
done

echo "[ok] replica set is writable"
