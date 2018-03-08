#!/usr/bin/python

""" Populate the Redis database. """

# Make sure print functions work in python2 and python3
from __future__ import print_function

import re
import os
import csv
import sys
import time
import zlib
try:
    import simplejson as json
except ImportError:
    import json
import optparse
from multiprocessing import Pipe, cpu_count

import querymod

loaded = {'metabolomics': [], 'macromolecules': [], 'chemcomps': []}
to_process = {'metabolomics': [], 'macromolecules': [], 'chemcomps': []}

# Load the configuration file
configuration = querymod.configuration

# Specify some basic information about our command
opt = optparse.OptionParser(usage="usage: %prog", version="1.0",
                            description="Update the entries in the Redis"
                                        " database.")
opt.add_option("--metabolomics", action="store_true", dest="metabolomics",
               default=False, help="Update the metabolomics entries.")
opt.add_option("--macromolecules", action="store_true", dest="macromolecules",
               default=False, help="Update the macromolecule entries.")
opt.add_option("--chemcomps", action="store_true", dest="chemcomps",
               default=False, help="Update the chemcomp entries.")
opt.add_option("--all", action="store_true", dest="all", default=False,
               help="Update all the entries.")
opt.add_option("--redis-db", action="store", dest="db", default=1,
               help="The Redis DB to use. 0 is master.")
opt.add_option("--flush", action="store_true", dest="flush", default=False,
               help="Flush all keys in the DB prior to reloading. This will "
               "interrupt service until the DB is rebuilt! (So only use it on"
               " the staging DB.)")
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
    entries = querymod.select(["Entry_ID"], "Release", database="metabolomics")
    entries = sorted(set(entries["Release.Entry_ID"]))
    for entry in entries:
        aent = (entry, "/share/subedit/metabolomics/%s/%s.str" % (entry, entry))
        to_process['metabolomics'].append(aent)

# Get the released entries from ETS
if options.macromolecules:
    conn, cur = querymod.get_postgres_connection(user=configuration['ets']['user'],
                                                 host=configuration['ets']['host'],
                                                 database=configuration['ets']['database'])
    cur.execute("SELECT bmrbnum FROM entrylog;")
    all_ids = [x[0] for x in cur.fetchall()]
    cur.execute("SELECT bmrbnum FROM entrylog WHERE status LIKE 'rel%';")
    valid_ids = sorted([int(x[0]) for x in cur.fetchall()])

    entry_fs_location = "/share/subedit/entries/bmr%d/clean/bmr%d_3.str"

    # Load the normal data
    for entry_id in valid_ids:
        cur_entry = [str(entry_id), entry_fs_location % (entry_id, entry_id)]
        to_process['macromolecules'].append(cur_entry)

# Load the chemcomps
if options.chemcomps:
    comp_ids = querymod.select(["BMRB_code"], "Entity", database="chemcomps")
    comp_ids = comp_ids['Entity.BMRB_code']
    chemcomps = ["chemcomp_" + x for x in comp_ids]
    to_process['chemcomps'].extend([[x, None] for x in chemcomps])

# Generate the flat list of entries to process
to_process['combined'] = (to_process['chemcomps'] +
                          to_process['macromolecules'] +
                          to_process['metabolomics'])

def clear_cache(r_conn, db_name):
    """ Delete the cache for a given schema."""

    for key in r_conn.scan_iter():
        if key.startswith("cache:%s" % db_name):
            r_conn.delete(key)
            print("Deleting cached query: %s" % key)

def one_entry(entry_name, entry_location, r_conn):
    """ Load an entry and add it to REDIS """

    if "chemcomp" in entry_name:
        try:
            ent = querymod.create_chemcomp_from_db(entry_name)
        except Exception as e:
            ent = None
            print("On %s: error: %s" % (entry_name, str(e)))

        if ent is not None:
            key = querymod.locate_entry(entry_name)
            r_conn.set(key, zlib.compress(ent.get_json()))
            print("On %s: loaded" % entry_name)
            return entry_name
    else:
        try:
            ent = querymod.pynmrstar.Entry.from_file(entry_location)

            print("On %s: loaded." % entry_name)
        except IOError as e:
            ent = None
            print("On %s: no file." % entry_name)
        except Exception as e:
            ent = None
            print("On %s: error: %s" % (entry_name, str(e)))

        if ent is not None:
            key = querymod.locate_entry(entry_name)
            r_conn.set(key, zlib.compress(ent.get_json()))
            return entry_name

def load_schemas(r):
    # Load the schemas into the DB
    orig_dir = os.getcwd()
    os.chdir("/tmp")
    os.system("svn checkout http://svn.bmrb.wisc.edu/svn/nmr-star-dictionary/ > /dev/null")
    os.chdir("nmr-star-dictionary")

    for rev in range(40, 222):

        # Handle old schema location
        schem_loc = "bmrb_only_files/adit_input"
        if rev < 163:
            schem_loc = "bmrb_star_v3_files/adit_input"

        os.system("svn update -r %s > /dev/null" % rev)
        with open("%s/xlschem_ann.csv" % schem_loc, "rU") as schem_file:
            a = csv.reader(schem_file)
            a.next()
            a.next()
            a.next()
            version = a.next()[3]
            # Don't copy any where the schema version isn't listed correctly
            if version.startswith("3"):
                clean_schema = querymod.pynmrstar.Schema("%s/xlschem_ann.csv" % schem_loc).get_json(serialize=False)
                with open("%s/adit_man_over.csv" % schem_loc, "rU") as over_ride_file:
                    override = csv.reader(over_ride_file)
                    headers = override.next()
                    override.next()
                    cc = ['Tag', 'Conditional tag', 'Override view value', 'Override value']
                    columns = [headers.index(x) for x in cc]
                    clean_schema['overrides'] = [[row[x] for x in columns] for row in override]
                r.set("schema:%s" % version, zlib.compress(json.dumps(clean_schema)))
                print("Set schema:%s" % version)

    os.system("rm -rfv adit_input")
    os.chdir(orig_dir)

# Since we are about to start, tell REDIS it is being updated
r = querymod.get_redis_connection(db=options.db)

# Load the schemas into REDIS
load_schemas(r)

# Flush the DB
if options.flush:
    print("Flushing the DB.")
    r.flushdb()

processes = []
num_threads = cpu_count()

for thread in xrange(0, num_threads):

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

def add_to_loaded(loaded_entry):
    """ The entry loaded successfully, so put it in the list of
    loaded entries of the appropriate type based on its name."""

    if loaded_entry.startswith("chemcomp"):
        loaded['chemcomps'].append(loaded_entry)
    elif loaded_entry.startswith("bm"):
        loaded['metabolomics'].append(loaded_entry)
    else:
        loaded['macromolecules'].append(loaded_entry)

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
                print("Not loaded.")
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

def natural_sort_key(s, _nsre=re.compile('([0-9]+)')):
    """ Use as a key to do a natural sort. 1<12<2<23."""

    return [int(text) if text.isdigit() else text.lower()
            for text in re.split(_nsre, s)]

# Put a few more things in REDIS
def make_entry_list(name):
    """ Calculate the list of entries to put in the DB."""

    # Sort the entries
    ent_list = sorted(loaded[name], key=natural_sort_key)

    # Get the old entry list and delete ones that aren't there anymore
    old_entries = r.lrange("%s:entry_list" % name, 0, -1)
    for each_entry in old_entries:
        if each_entry not in ent_list:
            to_delete = "%s:entry:%s" % (name, each_entry)
            if r.delete(to_delete):
                print("Deleted stale entry: %s" % to_delete)

    # Set the update time, ready status, and entry list
    r.hmset("%s:meta" % name, {"update_time": time.time(),
                               "num_entries": len(ent_list)})
    loading = "%s:entry_list" % name + "_loading"
    r.delete(loading)
    r.rpush(loading, *ent_list)
    r.rename(loading, "%s:entry_list" % name)

    dropped = [y[0] for y in to_process[name] if y[0] not in set(loaded[name])]
    print("Entries not loaded in DB %s: %s" % (name, dropped))

# Use a Redis list so other applications can read the list of entries
if options.metabolomics:
    make_entry_list('metabolomics')
    clear_cache(r, 'metabolomics')
if options.macromolecules:
    make_entry_list('macromolecules')
    clear_cache(r, 'macromolecules')
if options.chemcomps:
    make_entry_list('chemcomps')
    clear_cache(r, 'chemcomps')

# Make the full list from the existing lists regardless of update type
loaded['combined'] = (r.lrange('metabolomics:entry_list', 0, -1) +
                      r.lrange('macromolecules:entry_list', 0, -1) +
                      r.lrange('chemcomps:entry_list', 0, -1))
make_entry_list('combined')
