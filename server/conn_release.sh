#!/usr/bin/env bash

#git describe --abbrev=0 > wsgi/bmrbapi/version.txt
if ! docker build --network=host -t webapi .; then
  echo "Docker build failed."
  exit 2
fi


#
#docker run --name redis -p 6379:6379 -v /var/lib/redis:/data --restart=always -d redis

echo "Deploying docker instance..."
docker stop webapi
docker rm webapi
docker run -d --name webapi -p 9005:9001 -p9006:9000 --restart=always --link redis:redis --user 17473:10144 \
 --sysctl net.core.somaxconn=1024 \
 -v /tmp/logs:/opt/wsgi/logs \
 -v /tmp/.s.PGSQL.5432:/tmp/.s.PGSQL.5432 \
 -v /projects/BMRB/public/api/configuration.json:/opt/wsgi/bmrbapi/configuration.json \
 -v /projects/BMRB/depositions/timedomain_upload:/projects/BMRB/depositions/timedomain_upload \
 webapi
