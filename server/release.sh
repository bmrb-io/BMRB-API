#!/usr/bin/env bash

sudo docker stop webapi
sudo docker rm webapi

if [[ $# -eq 0 ]]; then
  git describe --abbrev=0 > wsgi/bmrbapi/version.txt
  if ! sudo docker build -t webapi .; then
    echo "Docker build failed."
    exit 2
  fi
fi

echo "Deploying docker instance..."
sudo docker tag webapi pike.bmrb.wisc.edu:5000/webapi
sudo docker push pike.bmrb.wisc.edu:5000/webapi

echo "sudo docker pull pike.bmrb.wisc.edu:5000/webapi; sudo docker stop webapi; sudo docker rm webapi; sudo docker run -d --name webapi -p 9002:9000 -p 9003:9001 --restart=always -v /websites/webapi/logs:/opt/wsgi/logs -v /websites/webapi/configuration.json:/opt/wsgi/bmrbapi/configuration.json pike.bmrb.wisc.edu:5000/webapi" | ssh web@herring
echo "sudo docker pull pike.bmrb.wisc.edu:5000/webapi; sudo docker stop webapi; sudo docker rm webapi; sudo docker run -d --name webapi -p 9002:9000 -p 9003:9001 --restart=always -v /websites/webapi/logs:/opt/wsgi/logs -v /websites/webapi/configuration.json:/opt/wsgi/bmrbapi/configuration.json pike.bmrb.wisc.edu:5000/webapi" | ssh web@blenny
