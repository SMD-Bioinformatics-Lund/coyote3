#!/bin/bash

CONTAINER_NAME="cdm_app"

echo "Hello!"

echo "Executing config update script:"
./scripts/update-to-latest-config.sh
return_code=$?

if [ ! $return_code == 0 ]; then
    echo "Failed to update config (script exited with non-zero status)."
    echo "Aborting update!"
    exit 1
fi

echo "Restarting $CONTAINER_NAME"
docker restart "$CONTAINER_NAME"
echo "All done."
echo "Bye."
