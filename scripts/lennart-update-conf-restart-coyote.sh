#!/bin/bash

#
# Copyright (c) 2025 Coyote3 Project Authors
# All rights reserved.
#
# This source file is part of the Coyote3 codebase.
# The Coyote3 project provides a framework for genomic data analysis,
# interpretation, reporting, and clinical diagnostics.
#
# Unauthorized use, distribution, or modification of this software or its
# components is strictly prohibited without prior written permission from
# the copyright holders.
#
#

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
