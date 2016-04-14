#!/bin/sh

yum install redis python-redis
systemctl enable redis
systemctl start redis

