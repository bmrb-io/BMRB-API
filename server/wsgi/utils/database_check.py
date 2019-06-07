#!/usr/bin/python

""" Verify the DB load worked. """

import sys
import logging
import optparse
import psycopg2

ETS_HOST = 'torpedo'
ETS_USER = 'ets'
ETS_DB = 'ETS'
ETS_PORT = 5432


def get_postgres_connection(user, host, database, port):
    """ Returns a connection to postgres and a cursor."""

    # Errors connecting will be handled upstream
    return psycopg2.connect(user=user, host=host, database=database, port=port).cursor()


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

logging.getLogger().setLevel(logging.DEBUG)

# Get the released entries from ETS
ets_cur = get_postgres_connection(user=ETS_USER, host=ETS_HOST, database=ETS_DB, port=ETS_PORT)
ets_cur.execute("SELECT bmrbnum FROM entrylog;")
all_ids = [x[0] for x in ets_cur.fetchall()]
ets_cur.execute("SELECT bmrbnum FROM entrylog WHERE status LIKE 'rel%';")
valid_ids = sorted([int(x[0]) for x in ets_cur.fetchall()])
match_count = 0

ets_cur.execute("SELECT bmrbnum from entrylog WHERE status LIKE 'rel%' AND !!!!!!!!!!!;")
recent_ids = ets_cur.fetchall()

db_cur = get_postgres_connection(user=options.user, host=options.host, database=options.database, port=options.port)

# Check that each of these entries has a record in the "Entry" table
for entry in recent_ids:
    logging.debug('Checking recent release %s' % entry)
    db_cur.execute('''SELECT "ID" FROM macromolecules."Entry" where entry= %s''', [entry])
    if len(db_cur.fetchall()) < 1:
        logging.exception('Recently released entry %s was not found in the DB!' % entry)
        sys.exit(1)

logging.info('Checking all entries are released.')
unreleased = set()
for entry in valid_ids:
    db_cur.execute('''SELECT "ID" FROM macromolecules."Entry" where entry= %s''', [entry])
    if len(db_cur.fetchall()) > 0:
        match_count += 1
    else:
        unreleased.add(entry)

if match_count < len(valid_ids):
    logging.exception('Fewer entries were in DB than were released in ETS!\nMissing IDs: %s' % unreleased)

