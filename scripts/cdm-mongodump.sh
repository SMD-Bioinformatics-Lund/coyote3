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

# Helper script to dump a subset of the mongodb running on lenanrt
# required to run CDM.
# Run as a part of dev-cdm-mongo/build.sh

mongodb_uri="mtlucmds1.lund.skane.se:27017"

# mongodb dump of dbs and collections required for running CMD

dbs_to_export="/cdm-mongodump.dbs.txt"
out_dir="/tmp/mongodump"
log_dir="/tmp/mongo_log"

echo "[START] Dumping CDM-related dbs and collections from  $dbs_to_export to $out_dir"

echo "[INFO] Creating outdir: $out_dir"
mkdir -p "$out_dir"

echo "[INFO] Creating logdir: $log_dir"
mkdir -p "$log_dir"

cdm_dump() {
    db="$1"
    collection="$2"
    mongodump -h "$mongodb_uri" -d "$db" -c "$collection" --out "$out_dir"
}

while read line; do
    echo "[INFO] CMD: cdm_dump $line"
    cdm_dump $line
done <  $dbs_to_export

echo "[INFO] Restoring from $out_dir"

#mongod --fork --logpath "$log_dir"
mongorestore --verbose "$out_dir"
#mongod --shutdown

echo "[EXIT] Bye."
