#!/bin/sh

yum install redis python-pip python-redis mod_evasive apache-gzip java-1.8.0-openjdk-headless

sudo pip install -r requirements.txt

# Configure redis installation
systemctl enable redis
systemctl start redis
systemctl enable redis-sentinel
systemctl start redis-sentinel

# Build FASTA
cd ../wsgi/submodules/fasta36/src
make -f ../make/Makefile.linux_sse2 all
