#!/bin/bash

# Fetch the latest version of the CDM config from
# github.com/Clinical-genomics-Lund/config-files and push to CDM

CONFIG_REPO_URL="git@github.com:Clinical-Genomics-Lund/config-files.git"
CONFIG_CURR_HASH_FILE="config.git.hash"

echo "Attempting to update CDM config"
echo "Fetching Clinical-Genomics-Lund/config-files hash"

latest_config_version="$(git ls-remote $CONFIG_REPO_URL HEAD | cut -f 1)"
curr_hash=""

if [ -f "$CONFIG_CURR_HASH_FILE" ]; then
    curr_hash=$(<"$CONFIG_CURR_HASH_FILE")
fi

if [ "$curr_hash" == "$latest_config_version" ]; then
    echo "Current config up to date (git hash: $curr_hash)."
    echo "Delete config.git.hash to force update!"
    echo "Exiting!"
    exit 1
fi

target_dir="$TMPDIR/cdm-deploy/config-files/$latest_config_version"

echo "Downloading updated config to: $target_dir"

if [ ! -d "$target_dir" ]; then
    mkdir -p "$target_dir"
    echo "Directory created: $target_dir"
    git clone $CONFIG_REPO_URL $target_dir
else
    echo "Directory already exists: $target_dir."
    echo "Attempting to set config from existing dir!"
fi

updated_config_dir="$target_dir/cdm/config"

if [ ! -d "$updated_config_dir" ]; then
    echo "cdm/config dir does not exist in $target_dir. Aborting update."
    exit 1
fi

cp -vr "$updated_config_dir" "."

# At the very end if successful:
echo "Writing: $latest_config_version -> $CONFIG_CURR_HASH_FILE"
echo "$latest_config_version" > "$CONFIG_CURR_HASH_FILE"
echo "Finished updating config from $curr_hash to $latest_config_version"
echo "Bye!"
