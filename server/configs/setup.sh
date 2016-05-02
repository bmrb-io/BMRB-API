#!/bin/sh

yum install redis python-redis python-psycopg2 python-flask mod-evasive

# Configure redis installation
systemctl enable redis
systemctl start redis
systemctl enable redis-sentinel
systemctl start redis-sentinel
