#!/bin/sh

# The postgresql10-contrib package is for pg_trgm
yum install redis python-pip python-virtualenv mod_evasive apache-gzip postgresql10-contrib

# Configure redis installation
systemctl enable redis
systemctl start redis
systemctl enable redis-sentinel
systemctl start redis-sentinel

# Build FASTA
cd ../wsgi/submodules/fasta36/src
make -f ../make/Makefile.linux_sse2 all

