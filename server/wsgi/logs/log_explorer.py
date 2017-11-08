#!/usr/bin/python3

import csv
import os, sys, json
import datetime
from urllib.parse import unquote

#os.system("cat /raid/www/admin/logs/api_json_v2.log* > /tmp/tmp.json")

scan_keys = {}
for arg in sys.argv[1:]:
    t,v = arg.split("=")
    scan_keys[t] = v

sw = set()
for line in open("tmp.json","r"):
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

#    if "instant" in d['path'] and d["local"] != True:
        #key = unquote(unquote(d['path'].replace("+", " "))).lower()
        #key = key[14:]
        #sw.add(key)


#ss = sorted(sw)
#with open("terms.csv", "w") as terms:
    #for key in ss:
        #writeit = True
        #cp = set(ss)
        #cp.remove(key)
        #for tk in cp:
            #if tk.startswith(key):
                #writeit = False
        #if writeit:
            #terms.write(key + "\n")
