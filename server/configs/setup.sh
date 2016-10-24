#!/bin/sh

yum install redis python-redis python-psycopg2 python-flask mod_evasive apache-gzip java-1.8.0-openjdk-headless

# Configure redis installation
systemctl enable redis
systemctl start redis
systemctl enable redis-sentinel
systemctl start redis-sentinel
