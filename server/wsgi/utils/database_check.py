#!/usr/bin/python

""" Verify the DB load worked. """

# Make sure print functions work in python2 and python3
from __future__ import print_function

import os
import sys
import time
import zlib
import optparse
import psycopg2


ETS_HOST = 'torpedo'
ETS_USER = 'ets'
ETS_DB = 'ETS'
ETS_PORT = 5432


def get_postgres_connection(user, host, database, port):
    """ Returns a connection to postgres and a cursor."""

    # Errors connecting will be handled upstream
    conn = psycopg2.connect(user=user, host=host, database=database, port=port)
    cur = conn.cursor()

    return conn, cur


# Specify some basic information about our command
opt = optparse.OptionParser(usage="usage: %prog", version="1.0",
                            description="Verify the database is loaded.")
opt.add_option("--host", action="store", dest="host",
               default="manta", help="Hostname of the machine with the PGDB to check.")
opt.add_option("--port", action="store", dest="port",
               default="5432", help="Port of the machine with the PGDB to check.")
opt.add_option("--database", action="store", dest="database",
               default="bmrbeverything", help="The name of the database that the data resides in.")
opt.add_option("--user", action="store", dest="user",
               default="bmrb", help="The user to use to connect to the database.")
# Parse the command line input
(options, cmd_input) = opt.parse_args()


# Get the released entries from ETS
ets_cur = get_postgres_connection(user=ETS_USER, host=ETS_HOST, database=ETS_DB, port=ETS_PORT)[1]
ets_cur.execute("SELECT bmrbnum FROM entrylog;")
all_ids = [x[0] for x in ets_cur.fetchall()]
ets_cur.execute("SELECT bmrbnum FROM entrylog WHERE status LIKE 'rel%';")
valid_ids = sorted([int(x[0]) for x in ets_cur.fetchall()])


db_cur = get_postgres_connection(user=options.user, host=options.host, database=options.database, port=options.port)[1]

# Check that each of these entries has a record in the "Entry" table
for entry in valid_ids:
    print('Checking %s' % entry)
    db_cur.execute('''SELECT bmrbid from entry where macromolecules."Entry" = %s''', [entry])
    print(len(db_cur.fetchall()))
