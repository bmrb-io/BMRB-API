#!/bin/sh

# The postgresql10-contrib package is for pg_trgm
yum install redis python-pip python-virtualenv mod_evasive apache-gzip postgresql10-contrib

# Configure redis installation
docker run --name redis -p 6379:6379 -v /var/lib/redis:/data --restart=always -d redis

# Build FASTA
cd ../wsgi/submodules/fasta36/src
make -f ../make/Makefile.linux_sse2 all

