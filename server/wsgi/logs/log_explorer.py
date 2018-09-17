#!/usr/bin/python3

import os
import sys
import json
import datetime


def log_generator(path='/raid/www/admin/logs/', default_name='api_json_v2.log'):
    for file_ in os.listdir(path):
        if file_.startswith(default_name):
            with open(os.path.join(path, file_), 'rU') as cur_file:
                lines = cur_file.readlines()
                for line in lines:
                    yield line


scan_keys = {}
for arg in sys.argv[1:]:
    t, v = arg.split("=")
    scan_keys[t] = v

for line in log_generator():
    d = json.loads(line)

    d['time'] = datetime.datetime.fromtimestamp(d['time']).strftime('%Y-%m-%d %H:%M:%S')

    te = {}
    show = True
    for key in scan_keys:
        te[key] = d[key]
        if scan_keys[key] not in str(d[key]):
            show = False
    if show:
        print(te)
