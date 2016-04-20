#!/usr/bin/python

import os
import json
import time
import redis
import cPickle

from utils import bmrb
from redis.sentinel import Sentinel
from multiprocessing import Pipe, cpu_count

loaded = []
to_process = []

# Load the configuration file
configuration = json.loads(open("api_config.json", "r").read())

# Figure out which REDIS to connect to
sentinel = Sentinel(configuration['redis']['sentinels'], socket_timeout=0.5)
redis_host, redis_port = sentinel.discover_master('tarpon_master')
print("Found REDIS host: %s" % redis_host)

# Load the metabalomics data
for one_dir in os.listdir("/share/subedit/metabolomics/"):
    to_process.append([str(one_dir), os.path.join("/share/subedit/metabolomics/", one_dir, one_dir + ".str")])

# Load the normal data
for x in xrange(0,35000):
    to_process.append([str(x), "/share/subedit/entries/bmr%d/clean/bmr%d_3.str" % (x,x)])

def one_entry(entry_name, entry_location, r):
    """ Load an entry and add it to REDIS """
    try:
        ent = bmrb.entry.fromFile(entry_location)
        print("On %s: loaded." % entry_name)
    except IOError as e:
        ent = None
        print("On %s: no file." % entry_name)
    except Exception as e:
        ent = None
        print("On %s: error: %s" % (entry_name, str(e)))

    r.set(entry_name, cPickle.dumps(ent))
    if ent:
        return entry_name

processes = []
num_threads = cpu_count()

for thread in xrange(0,num_threads):

    # Set up the pipes
    parent_conn, child_conn = Pipe()
    # Start the process
    processes.append([parent_conn, child_conn])

    # Use the fork to get through!
    newpid = os.fork()
    # Okay, we are the child
    if newpid == 0:

        # Each child gets a REDIS
        red = redis.StrictRedis(host=redis_host, port=redis_port, password=configuration['redis']['password'])
        child_conn.send("ready")
        while True:
            parent_message = child_conn.recv()
            if parent_message == "die":
                print "I am child %d and have finished my work" % thread
                child_conn.close()
                parent_conn.close()
                os._exit(0)

            # Do work based on parent_message
            result = one_entry(parent_message[0], parent_message[1], red)

            # Tell our parent we are ready for the next job
            child_conn.send(result)

    # We are the parent, don't need the child connection
    else:
        child_conn.close()

# Check if entries have completed by listening on the sockets
while len(to_process) > 0:

    time.sleep(.001)
    # Poll for processes ready to listen
    for proc in processes:
        if proc[0].poll():
            data = proc[0].recv()
            if data and data != "ready":
                loaded.append(data)
            proc[0].send(to_process.pop())
            break

# Reap the children
for thread in xrange(0, num_threads):
    # Get the last ready message from the child
    data = processes[thread][0].recv()
    # Tell the child to shut down
    processes[thread][0].send("die")

    res = os.wait()
    if data:
        loaded.append(data)

# Put a few more things in REDIS
r = redis.StrictRedis(host=redis_host, port=redis_port, password=configuration['redis']['password'])
r.set("schema", cPickle.dumps(bmrb.schema()))
r.set("loaded", cPickle.dumps(loaded))

try:
    r.save()
except redis.exceptions.ResponseError:
    print("REDIS was already saving. Waiting and trying again.")
    time.sleep(120)
    r.save()
