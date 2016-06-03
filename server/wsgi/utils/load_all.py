#!/usr/bin/python

import os
import sys
import json
import time
import zlib

import querymod
from multiprocessing import Pipe, cpu_count

loaded = []
to_process = []

# Load the configuration file
configuration = querymod.configuration

# Figure out which REDIS to connect to
redis_db = 1

# By default put data into a "staging" db. Only put it in master if they
#  specify the first argument as "master"
if len(sys.argv) > 1 and sys.argv[1] == "master":
    redis_db = 0
    print("Operating on master DB.")
else:
    print("Operating on staging DB.")

# Load the metabalomics data
for one_dir in os.listdir("/share/subedit/metabolomics/"):
    to_process.append([str(one_dir), os.path.join("/share/subedit/metabolomics/", one_dir, one_dir + ".str")])

# Get the released entries from ETS
conn, cur = querymod.get_postgres_connection(user=configuration['ets']['user'],
                                             host=configuration['ets']['host'],
                                             database=configuration['ets']['database'])
cur.execute("SELECT bmrbnum FROM entrylog;")
all_ids = [x[0] for x in cur.fetchall()]
cur.execute("SELECT bmrbnum FROM entrylog WHERE status LIKE 'rel%';")
valid_ids = [x[0] for x in cur.fetchall()]

# Load the normal data
for entry_id in valid_ids:
    to_process.append([str(entry_id), "/share/subedit/entries/bmr%d/clean/bmr%d_3.str" % (entry_id, entry_id)])

def one_entry(entry_name, entry_location, r):
    """ Load an entry and add it to REDIS """

    if "chemcomp" in entry_name:
        ent = querymod.create_chemcomp_from_db(entry_name)
        r.set(entry_name, zlib.compress(ent.getJSON()))
        return entry_name
    else:
        try:
            ent = querymod.bmrb.entry.fromFile(entry_location)

            print("On %s: loaded." % entry_name)
        except IOError as e:
            ent = None
            print("On %s: no file." % entry_name)
        except Exception as e:
            ent = None
            print("On %s: error: %s" % (entry_name, str(e)))

        if ent != None:
            r.set(entry_name, zlib.compress(ent.getJSON()))
            return entry_name

# Since we are about to start, tell REDIS it is being updated
r = querymod.get_redis_connection(db=redis_db)

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
        red = querymod.get_redis_connection(db=redis_db)
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

# We are starting to update
r.set("ready", 0)

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

# Delete all entries that might have been withdrawn
for x in all_ids:
    if x not in valid_ids:
        if r.delete(x) == 1:
            print("Deleting entry that is no longer valid: %d" % x)

# Put a few more things in REDIS

# Use a REDIS list so other applications can read the list of entries
for x in sorted(loaded):
    r.rpush("loading", x)
r.rename("loading", "loaded")

# Set the time
r.set("update_time", time.time())

# Set the ready state
r.set("ready", 1)
