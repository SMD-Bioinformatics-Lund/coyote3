#!/bin/sh
set -eu
attempt=0
until mongosh --host demo-mongo:27017 --username demo_root \
  --password "$MONGO_INITDB_ROOT_PASSWORD" --authenticationDatabase admin --quiet --eval '
  const config = db.getSiblingDB("local").system.replset.findOne();
  if (config === null) {
    rs.initiate({_id: "coyote-demo-rs", members: [{_id: 0, host: "demo-mongo:27017"}]});
  } else if (config._id !== "coyote-demo-rs" || config.members.length !== 1 ||
             config.members[0].host !== "demo-mongo:27017") {
    throw new Error("Unexpected demo replica-set topology");
  }
  if (!db.hello().isWritablePrimary) quit(1);
  ' >/dev/null; do
  attempt=$((attempt + 1))
  if [ "$attempt" -ge 60 ]; then
    echo "Demo MongoDB did not become a writable replica-set primary" >&2
    exit 1
  fi
  sleep 2
done
