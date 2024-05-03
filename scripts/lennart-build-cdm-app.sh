#!/bin/bash

echo "Hello."

if [[ -f ".env" ]]
then
    echo ".env exists in project root. Sourcing!"
    source .env
fi

# Subpath at which CDM is hosted:
SCRIPT_NAME="/cdm"

# Port number to host CDM at
PORT_NBR=5801

# Build CDM docker image and start on lennart
version=$(python ./cdm/__version__.py)
echo "Deploying CDM v${version} on lennart."

image_name="cdm:$version"
container_name="cdm_app"

# Fail build if unable to access CDM secret key:
if [[ -z "${SECRET_KEY_CDM_PATH}" ]]; then
    echo "SECRET_KEY_CDM_PATH is undefined. Exiting."
    exit 1
else
    echo "Accessing SECRET KEY. Sudo privileges required!"
    SECRET_KEY=$(python "$SECRET_KEY_CDM_PATH")
fi

# Warn if unable to access Alamut key/institution:
if [[ -z "${ALAMUT_API_KEY_PATH}" ]]; then
    echo "Warning! ALAMUT_API_KEY_PATH is undefined. Did you set it in .env?"
else
    echo "Accessing ALAMUT API KEY. Sudo privileges required!"
    ALAMUT_API_KEY=$(bash "$ALAMUT_API_KEY_PATH")
fi

if [[ -z "${ALAMUT_INSTITUTION}" ]]; then
    echo "Warning! ALAMUT_API_KEY_PATH is undefined. Did you set it in .env?"
fi

echo "Running configuration update script."
./scripts/update-to-latest-config.sh

echo "Building docker image: '$image_name'"
docker build --no-cache --network host --target cdm_app -t "$image_name" .

docker stop cdm_app
docker rm cdm_app

echo "Starting docker container $container_name"
docker run \
       -e FLASK_MONGO_HOST='172.17.0.1' \
       -e FLASK_MONGO_PORT='27017' \
       -e FLASK_DEBUG=0 \
       -e SCRIPT_NAME=${SCRIPT_NAME} \
       -e FLASK_BAM_ALAMUT_API_KEY=${ALAMUT_API_KEY} \
       -e FLASK_BAM_ALAMUT_INSTITUTION=${ALAMUT_INSTITUTION} \
       -e FLASK_SECRET_KEY=${SECRET_KEY} \
       -e TZ='Europe/Stockholm' \
       --mount type=bind,source="$(pwd)"/config,target=/app/config \
       -p "$PORT_NBR:8000" \
       --name "$container_name" \
       --restart=always \
       -d \
       "$image_name"

echo "Done!"
echo "Bye."
