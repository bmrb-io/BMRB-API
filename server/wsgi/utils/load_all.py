#!/usr/bin/python

import os
import sys
import time
import cPickle
from subprocess import Popen, PIPE
from multiprocessing import Pipe, cpu_count

import bmrb

import optparse
# Specify some basic information about our command
optparser = optparse.OptionParser(usage="usage: %prog server|generator [options]", version="1", description="Prepare entries for loading into REDIS (generator) or load entries into REDIS (server).")
optparser.add_option("--metabolomics-directory", action="store", dest="metabolomics", default="/share/subedit/metabolomics/", type="string", help="Location of the metabolomics entries.")
optparser.add_option("--entry-directory", action="store", dest="entries", default="/share/subedit/entries/", type="string", help="Location of the normal entries.")
optparser.add_option("--output-directory", action="store", dest="outdir", default="/zfs/entry_pickles", type="string", help="Location to write the pickles.")
optparser.add_option("--input-directory", action="store", dest="indir", default="/raid/www/bmrbapi/redis_reload", type="string", help="Location to read entries from.")

# Options, parse 'em
(options, cmd_input) = optparser.parse_args()

# See which mode
if len(cmd_input) == 0:
    print("You must specify the mode as the first argument: either 'server' or 'generator'.")
    sys.exit(1)
if cmd_input[0] != "server" and cmd_input[0] != "generator":
    print("Invalid mode specified. Choose: 'server' or 'generator'.")
    sys.exit(2)


# Generate the pickles
if cmd_input[0] == "generator":

    loaded = []
    to_process = []

    def write_redis_object(key, value):
        """ Write a key to the folder that will eventually be loaded into REDIS."""
        with open(os.path.join(options.outdir, key), "w") as the_file:
            the_file.write(cPickle.dumps(value))


    # Write that we are processing. If the server sees this key value it bad it can flip out
    write_redis_object("ready", False)

    # Load the metabalomics data
    for one_dir in os.listdir(options.metabolomics):
        to_process.append([str(one_dir), os.path.join(options.metabolomics, one_dir, one_dir + ".str")])

    # Load the normal data
    for x in xrange(0,35000):
        to_process.append([str(x), options.entries + "/bmr%d/clean/bmr%d_3.str" % (x,x)])

    def one_entry(entry_name, entry_location):
        """ Load an entry and add it to the output directory. """
        try:
            ent = bmrb.entry.fromFile(entry_location)
            sys.stdout.write("On %s: loaded.\n" % entry_name)
        except IOError as e:
            ent = None
            sys.stderr.write("On %s: no file.\n" % entry_name)
        except Exception as e:
            ent = None
            sys.stderr.write("On %s: error: %s\n" % (entry_name, str(e)))

        # Write the file to disk
        write_redis_object(entry_name, ent)

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
            child_conn.send("ready")
            while True:
                parent_message = child_conn.recv()
                if parent_message == "die":
                    print "I am child %d and have finished my work" % thread
                    child_conn.close()
                    parent_conn.close()
                    os._exit(0)

                # Do work based on parent_message
                result = one_entry(parent_message[0], parent_message[1])

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
                if data:
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

    # Write the metadata
    write_redis_object("schema", bmrb.schema())
    write_redis_object("loaded", loaded)
    write_redis_object("ready", True)

# Load the directory on the server
elif cmd_input[0] == "server":

    import redis

    # Load everything into REDIS
    r = redis.StrictRedis()

    # Load the keys into REDIS
    for one_file in os.listdir(options.indir):
        r.set(one_file, open(os.path.join(options.indir, one_file),  "r").read())

    # Save
    try:
        r.save()
    except redis.exceptions.ResponseError:
        print "REDIS was already saving. Waiting and trying again."
        time.sleep(120)
        r.save()
