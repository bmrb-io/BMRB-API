#!/bin/sh

yum install redis python-redis mod_evasive apache-gzip java-1.8.0-openjdk-headless

sudo pip install flask psycopg2

# Configure redis installation
systemctl enable redis
systemctl start redis
systemctl enable redis-sentinel
systemctl start redis-sentinel
