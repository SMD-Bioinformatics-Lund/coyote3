#!/bin/bash

echo "Hello."

if [[ -f ".alpha_env" ]]
then
    echo ".env exists in project root. Sourcing!"
    source .alpha_env
fi

# Subpath at which Coyote3 is hosted:
# SCRIPT_NAME="/coyote3"
SCRIPT_NAME=""

# Port number to host Coyote3 at
PORT_NBR=5815

# Build Coyote3 docker image and start on lennart
version=$(python ./coyote/__version__.py)
echo "Deploying Coyote3 v${version} on lennart."

image_name="coyote3:$version"
container_name="coyote3_app_alpha-2"

# # Fail build if unable to access Coyote secret key:
# if [[ -z "${SECRET_KEY_COYOTE_PATH}" ]]; then
#     echo "SECRET_KEY_COYOTE_PATH is undefined. Exiting."
#     exit 1
# else
#     echo "Accessing SECRET KEY. Sudo privileges required!"
#     SECRET_KEY=$(python "$SECRET_KEY_COYOTE_PATH")
# fi

# Warn if unable to access Alamut key/institution:
# if [[ -z "${ALAMUT_API_KEY_PATH}" ]]; then
#     echo "Warning! ALAMUT_API_KEY_PATH is undefined. Did you set it in .env?"
# else
#     echo "Accessing ALAMUT API KEY. Sudo privileges required!"
#     ALAMUT_API_KEY=$(bash "$ALAMUT_API_KEY_PATH")
# fi

# if [[ -z "${ALAMUT_INSTITUTION}" ]]; then
#     echo "Warning! ALAMUT_API_KEY_PATH is undefined. Did you set it in .env?"
# fi

# echo "Running configuration update script."
# ./scripts/update-to-latest-config.sh

echo "Building docker image: '$image_name'"
docker build --no-cache --network host --target coyote3_app -t "$image_name" . 

docker stop coyote3_app_alpha
docker rm coyote3_app_alpha

echo "Starting docker container $container_name"
# echo -e "docker run -e FLASK_MONGO_HOST=172.17.0.1 -e FLASK_MONGO_PORT=27017 -e FLASK_DEBUG=0 -e SCRIPT_NAME=${SCRIPT_NAME} -e TZ=Europe/Stockholm --dns 10.212.226.10 --mount type=bind,source=$(pwd)/config,target=/app/config  -v ./logs:/app/logs -p $PORT_NBR:8000 --name $container_name --restart=always -d $image_name"

#docker run -e FLASK_MONGO_HOST=172.20.0.1 -e FLASK_MONGO_PORT=27017 -e FLASK_DEBUG=0 -e SCRIPT_NAME='' -e TZ=Europe/Stockholm --dns 10.212.226.10 -v /data/bnf/dev/ram/Pipelines/Web_Developement/coyote_blueprinted/config:/app/config  -v /data/bnf/dev/ram/Pipelines/Web_Developement/coyote_blueprinted/logs:/app/logs -p 5814:8000 --name coyote3_app --restart=always -d coyote3:3.0.0

#docker run -e DB_HOST=$DB_HOST -e DB_PORT=$DB_PORT -e FLASK_DEBUG=1 -e SCRIPT_NAME=$SCRIPT_NAME -e LOG_LEVEL="DEBUG" -p 5813:5000 --dns "10.212.226.10" --name cll_genie_app_dev -v /data/lymphotrack/cll_results/:/cll_genie/results/ -v /data/lymphotrack/cll_results_dev/:/cll_genie/results_dev/ -v /data/lymphotrack/results/lymphotrack_dx/:/data/lymphotrack/results/lymphotrack_dx/ -v /data/lymphotrack/logs:/cll_genie/logs -d "cll_genie:$version"

docker run \
        -e FLASK_MONGO_HOST='172.17.0.1' \
        -e FLASK_MONGO_PORT='27017' \
        -e FLASK_DEBUG=0 \
        -e SCRIPT_NAME=${SCRIPT_NAME} \
        -e FLASK_SECRET_KEY=${SECRET_KEY} \
        -e TZ='Europe/Stockholm' \
        --dns "10.212.226.10" \
        -v $PWD/config:/app/config \
        -v $PWD/logs:/app/logs \
        -v /access:/access \
	-v /media:/media \
        -v /data:/data \
        -p "$PORT_NBR:8000" \
        --name "$container_name" \
        --restart=always \
        -d \
        "$image_name"

echo "Done!"
echo "Bye."

    #    -e FLASK_BAM_ALAMUT_API_KEY=${ALAMUT_API_KEY} \
    #    -e FLASK_BAM_ALAMUT_INSTITUTION=${ALAMUT_INSTITUTION} \
    #    -e FLASK_SECRET_KEY=${SECRET_KEY} \
