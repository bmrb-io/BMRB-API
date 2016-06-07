#!/usr/bin/python

import os
import sys
import json
import time
import zlib
import optparse
import querymod
from multiprocessing import Pipe, cpu_count

loaded = {'metabolomics': [], 'macromolecules': [], 'chemcomps': []}
to_process = {'metabolomics': [], 'macromolecules': [], 'chemcomps': []}

# Load the configuration file
configuration = querymod.configuration

# Specify some basic information about our command
opt = optparse.OptionParser(usage="usage: %prog", version="1.0", description="Update the entries in the Redis database.")
opt.add_option("--metabolomics", action="store_true", dest="metabolomics", default=False, help="Update the metabolomics entries.")
opt.add_option("--macromolecules", action="store_true", dest="macromolecules", default=False, help="Update the macromolecule entries.")
opt.add_option("--chemcomps", action="store_true", dest="chemcomps", default=False, help="Update the chemcomp entries.")
opt.add_option("--all", action="store_true", dest="all", default=False, help="Update all the entries.")
opt.add_option("--redis-db", action="store", dest="db", default=1, help="The Redis DB to use. 0 is master.")
opt.add_option("--flush", action="store_true", dest="flush", default=False, help="Flush all keys in the DB prior to reloading. This will interrupt service until the DB is rebuilt! (So only use it on the staging DB.")
# Parse the command line input
(options, cmd_input) = opt.parse_args()

# Make sure they specify a DB
if not (options.metabolomics or options.macromolecules or
        options.chemcomps or options.all):
    print("You must specify which entries to load.")
    sys.exit(1)

# Update the values if all is presented
if options.all:
    options.metabolomics = True
    options.macromolecules = True
    options.chemcomps = True

if options.metabolomics and options.macromolecules and options.chemcomps:
    options.all = True

# Load the metabolomics data
if options.metabolomics:
    entries = querymod.get_fields_by_fields(["Entry_ID"],
                                            "Release",
                                            schema="metabolomics")
    entries = sorted(set(entries["Release.Entry_ID"]))
    for entry in entries:
        ent = (entry, "/share/subedit/metabolomics/%s/%s.str" % (entry, entry))
        to_process['metabolomics'].append(ent)

# Get the released entries from ETS
if options.macromolecules:
    conn, cur = querymod.get_postgres_connection(user=configuration['ets']['user'],
                                                 host=configuration['ets']['host'],
                                                 database=configuration['ets']['database'])
    cur.execute("SELECT bmrbnum FROM entrylog;")
    all_ids = [x[0] for x in cur.fetchall()]
    cur.execute("SELECT bmrbnum FROM entrylog WHERE status LIKE 'rel%';")
    valid_ids = sorted([int(x[0]) for x in cur.fetchall()])

    # Load the normal data
    for entry_id in valid_ids:
        to_process['macromolecules'].append([str(entry_id), "/share/subedit/entries/bmr%d/clean/bmr%d_3.str" % (entry_id, entry_id)])

# Load the chemcomps
if options.chemcomps:
    chemcomps = ["chemcomp_" + x for x in querymod.get_fields_by_fields(["BMRB_code"], "Entity", schema="chemcomps")['Entity.BMRB_code']]
    to_process['chemcomps'].extend([[x, None] for x in chemcomps])

# Generate the flat list of entries to process
to_process['combined'] = (to_process['chemcomps'] +
                          to_process['macromolecules'] +
                          to_process['metabolomics'])

def one_entry(entry_name, entry_location, r):
    """ Load an entry and add it to REDIS """

    if "chemcomp" in entry_name:
        try:
            ent = querymod.create_chemcomp_from_db(entry_name)
        except Exception as e:
            ent = None
            print("On %s: error: %s" % (entry_name, str(e)))

        if ent is not None:
            r.set(entry_name, zlib.compress(ent.getJSON()))
            r.expire(entry_name, 2678400)
            print("On %s: loaded" % entry_name)
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

        if ent is not None:
            r.set(entry_name, zlib.compress(ent.getJSON()))
            r.expire(entry_name, 2678400)
            return entry_name

# Since we are about to start, tell REDIS it is being updated
r = querymod.get_redis_connection(db=options.db)

# Flush the DB
if options.flush:
    print("Flushing the DB.")
    r.flushdb()

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

        # Each child gets a Redis
        red = querymod.get_redis_connection(db=options.db)
        child_conn.send("ready")
        while True:
            parent_message = child_conn.recv()
            if parent_message == "die":
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
time.sleep(1)
r.set("ready", 0)

def add_to_loaded(entry):
    if data.startswith("chemcomp"):
        loaded['chemcomps'].append(data)
    elif data.startswith("bm"):
        loaded['metabolomics'].append(data)
    else:
        loaded['macromolecules'].append(data)

# Check if entries have completed by listening on the sockets
while len(to_process['combined']) > 0:

    time.sleep(.001)
    # Poll for processes ready to listen
    for proc in processes:
        if proc[0].poll():
            data = proc[0].recv()
            if data:
                if data != "ready":
                    add_to_loaded(data)
            else:
                print "Not loaded."
            proc[0].send(to_process['combined'].pop())
            break

# Reap the children
for thread in xrange(0, num_threads):
    # Get the last ready message from the child
    data = processes[thread][0].recv()
    # Tell the child to shut down
    processes[thread][0].send("die")

    res = os.wait()
    if data:
        add_to_loaded(data)

# Put a few more things in REDIS
def make_entry_list(name, values):
    loading = name + "_loading"
    r.delete(loading)
    r.rpush(loading, *sorted(values))
    r.rename(loading, name)
    r.expire(name, 2678400)

def print_dropped(db):
    dropped = [x[0] for x in to_process[db] if x[0] not in set(loaded[db])]
    print("Entries not loaded in DB %s: %s" % (db, dropped))

# Use a Redis list so other applications can read the list of entries
if options.metabolomics:
    make_entry_list('metabolomics', loaded['metabolomics'])
    print_dropped('metabolomics')
if options.macromolecules:
    make_entry_list('macromolecules', loaded['macromolecules'])
    print_dropped('macromolecules')
if options.chemcomps:
    make_entry_list('chemcomps', loaded['chemcomps'])
    print_dropped('chemcomps')

# Make the full list from the existing lists regardless of update type
loaded['combined'] = (r.lrange('metabolomics', 0, -1) +
                      r.lrange('macromolecules', 0, -1) +
                      r.lrange('chemcomps', 0, -1))
make_entry_list('combined', loaded['combined'])

# Set the time
r.set("update_time", time.time())

# Set the ready state
r.set("ready", 1)
