#!/bin/sh

yum install redis python-redis python-psycopg2
systemctl enable redis
systemctl start redis

