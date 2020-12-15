#!/bin/sh

# The postgresql12-contrib package is for pg_trgm
yum install mod_proxy_uwsgi postgresql12-contrib

# This line needs to be added somewhere in HTTPD configuration:
#  LoadModule proxy_uwsgi_module modules/mod_proxy_uwsgi.so

# Configure redis installation
docker run --name redis -p 6379:6379 -v /var/lib/redis:/data --restart=always -d redis
