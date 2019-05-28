#!/usr/bin/env bash

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null 2>&1 && pwd )"

sudo docker stop bmrbapi
sudo docker rm bmrbapi

if [[ $# -eq 0 ]]
  then

    if ! sudo docker build -t bmrbapi .; then
      echo "Docker build failed."
      exit 2
    fi
    echo "Running in development mode."
    sudo docker run -d --name bmrbapi -p 9001:9001 --restart=always -v /zfs/git/BMRB-API/server/configs/api_config.json:/opt/wsgi/configuration.json bmrbapi
fi
