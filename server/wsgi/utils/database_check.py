#!/usr/bin/env python

""" Verify the DB load worked. """

import sys
import logging
import optparse
import psycopg2
import datetime


def get_postgres_connection(user, host, database, port):
    """ Returns a connection to postgres and a cursor."""

    # Errors connecting will be handled upstream
    return psycopg2.connect(user=user, host=host, database=database, port=port).cursor()


# Specify some basic information about our command
opt = optparse.OptionParser(usage="usage: %prog", version="1.0",
                            description="Verify the database is loaded.")
opt.add_option("--host", action="store", dest="host",
               default="manta", help="Hostname of the machine with the DB to check.")
opt.add_option("--port", action="store", dest="port",
               default="5432", help="Port of the machine with the DB to check.")
opt.add_option("--database", action="store", dest="db",
               default="bmrbeverything", help="The name of the database that the data resides in.")
opt.add_option("--user", action="store", dest="user",
               default="bmrb", help="The user to use to connect to the database.")

opt.add_option("--ets-host", action="store", dest="ets_host",
               default="torpedo", help="Hostname of the machine with the ETS DB to check.")
opt.add_option("--ets-port", action="store", dest="ets_port",
               default="5432", help="Port of the machine with the ETS PGDBDB to check.")
opt.add_option("--ets-database", action="store", dest="ets_db",
               default="ETS", help="The name of the ETS database that the data resides in.")
opt.add_option("--ets-user", action="store", dest="ets_user",
               default="ets", help="The user to use to connect to the ETS database.")

opt.add_option("--level", action="store", dest="level", type='choice',
               choices=['debug', 'info', 'warning', 'error', 'critical'],
               default="warning", help="The log level to use.")
# Parse the command line input
(options, cmd_input) = opt.parse_args()

logging.getLogger().setLevel({'debug': logging.DEBUG, 'info': logging.INFO, 'warning': logging.WARNING,
                              'error': logging.ERROR, 'critical': logging.CRITICAL}[options.level])

offsets = """
fri -> 8 days to 1 day
sat -> 9 days to 2 day
sun -> 10 days to 3 day
mon -> 11 days to 4 day
tues -> 12 days to 5 day
wed -> 13 days to 6 days
thurs -> 7 days to 0 days"""

ending_offset = (datetime.date.today().isoweekday() + 3) % 7
starting_offset = ending_offset + 7

# Get the released entries from ETS
ets_cur = get_postgres_connection(user=options.ets_user, host=options.ets_host,
                                  database=options.ets_db, port=options.ets_port)
ets_cur.execute("SELECT bmrbnum FROM entrylog;")
all_ids = [x[0] for x in ets_cur.fetchall()]
ets_cur.execute('''
SELECT bmrbnum FROM entrylog
  WHERE status LIKE 'rel%%'
  AND release_date < current_date - interval \'%s days\'''' % ending_offset)
valid_ids = sorted([int(x[0]) for x in ets_cur.fetchall()])

# Cut off at least 1 day before DB run date
# ending_offset += 1
logging.info('Checking entries released from %d to %d days ago.' % (starting_offset, ending_offset))

ets_cur.execute('''
SELECT bmrbnum from entrylog 
  WHERE status LIKE 'rel%%'
    AND release_date > current_date - interval '%s days'
    AND release_date < current_date - interval '%s days' ''' % (starting_offset, ending_offset))
recent_ids = ets_cur.fetchall()

db_cur = get_postgres_connection(user=options.user, host=options.host, database=options.db, port=options.port)

# Check that each of these entries has a record in the "Entry" table
for entry in recent_ids:
    logging.debug('Checking recent release %s' % entry)
    db_cur.execute('''SELECT "ID" FROM macromolecules."Entry" where "ID" = '%s' ''', [entry[0]])
    if len(db_cur.fetchall()) < 1:
        logging.exception('Recently released entry %s was not found in the DB!' % entry)
        sys.exit(1)

logging.info('Checking all entries are released.')
joined = ''.join(''' "ID" = '%s' OR ''' % x for x in valid_ids) + ' 1 = 2'
db_cur.execute('SELECT "ID" FROM macromolecules."Entry" where ' + joined)
released = set([int(x[0]) for x in db_cur.fetchall()])

unreleased = set(valid_ids) - released
if len(unreleased) > 36:
    logging.warning('More than 36 entries show as released in ETS but are missing data in'
                    ' the DB! Number of missing entries: %s' % len(unreleased))
    sys.exit(2)

# Verify some important tables manually
db_cur.execute('SELECT count(*) FROM macromolecules."Atom_chem_shift"')
num_shifts = db_cur.fetchone()[0]
if num_shifts < 9593166:
    logging.warning('Fewer macromolecule chemical shifts than expected! Only found %s.' % num_shifts)
    sys.exit(3)

db_cur.execute('SELECT count(*) FROM macromolecules."Atom_chem_shift"')
num_shifts = db_cur.fetchone()[0]
if num_shifts < 65210:
    logging.warning('Fewer metabolomics chemical shifts than expected! Only found %s.' % num_shifts)
    sys.exit(4)

db_cur.execute('SELECT count(*) FROM macromolecules."Software"')
num_shifts = db_cur.fetchone()[0]
if num_shifts < 34119:
    logging.warning('Fewer macromolecule software rows than expected! Only found %s.' % num_shifts)
    sys.exit(5)

