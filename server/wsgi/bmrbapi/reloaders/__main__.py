#!/usr/bin/env python

""" Populate the Redis and PSQL databases. """

import logging
import multiprocessing
import optparse
import os
import re
import sys
import time

from bmrbapi.reloaders.database import one_entry
from bmrbapi.reloaders.inext import inext
from bmrbapi.reloaders.molprobity import molprobity_full, molprobity_visualizations
from bmrbapi.reloaders.sql_initialize import sql_initialize
from bmrbapi.reloaders.timedomain import timedomain
from bmrbapi.reloaders.uniprot import uniprot
from bmrbapi.reloaders.xml_generate import xml
from bmrbapi.utils.configuration import configuration
from bmrbapi.utils.connections import PostgresConnection, RedisConnection

loaded = {'metabolomics': [], 'macromolecules': [], 'chemcomps': []}
to_process = {'metabolomics': [], 'macromolecules': [], 'chemcomps': []}


def add_to_loaded(loaded_entry):
    """ The entry loaded successfully, so put it in the list of
    loaded entries of the appropriate type based on its name."""

    if not loaded_entry:
        return

    if loaded_entry.startswith("chemcomp"):
        loaded['chemcomps'].append(loaded_entry)
    elif loaded_entry.startswith("bm"):
        loaded['metabolomics'].append(loaded_entry)
    else:
        loaded['macromolecules'].append(loaded_entry)


def _natural_sort_key(s, _nsre=re.compile('([0-9]+)')):
    """ Use as a key to do a natural sort. 1<12<2<23."""

    if type(s) == bytes:
        s = s.decode()

    return [int(text) if text.isdigit() else text.lower()
            for text in re.split(_nsre, s)]


# Put a few more things in REDIS
def make_entry_list(name: str):
    """ Calculate the list of entries to put in the DB."""

    # Sort the entries
    ent_list = sorted(loaded[name], key=_natural_sort_key)

    if len(ent_list) == 0:
        logging.critical('Could not load the entry set %s - no entries located!', name)
        return

    # Get the old entry list and delete ones that aren't there anymore
    old_entries = r_conn.lrange("%s:entry_list" % name, 0, -1)
    for each_entry in old_entries:
        if each_entry not in ent_list:
            to_delete = "%s:entry:%s" % (name, each_entry)
            if r_conn.delete(to_delete):
                logging.info("Deleted stale entry: %s" % to_delete)

    # Set the update time, ready status, and entry list
    r_conn.hset(f"{name}:meta", mapping={"update_time": time.time(), "num_entries": len(ent_list)})
    loading = f"{name}:entry_list_loading"
    r_conn.delete(loading)
    r_conn.rpush(loading, *ent_list)
    r_conn.rename(loading, f"{name}:entry_list")

    dropped = [y[0] for y in to_process[name] if y[0] not in set(loaded[name])]
    logging.info("Entries not loaded in DB %s: %s" % (name, dropped))


# Specify some basic information about our command
opt = optparse.OptionParser(usage="usage: %prog", version="1.0",
                            description="Update the entries in the Redis database.")
opt.add_option("--metabolomics", action="store_true", dest="metabolomics", default=False,
               help="Update the metabolomics entries.")
opt.add_option("--macromolecules", action="store_true", dest="macromolecules", default=False,
               help="Update the macromolecule entries.")
opt.add_option("--chemcomps", action="store_true", dest="chemcomps", default=False, help="Update the chemcomp entries.")
opt.add_option("--molprobity-visualization", action="store_true", dest="molprobity_visualization", default=False,
               help="Update the MolProbity visualization tables.")
opt.add_option("--molprobity-full", action="store_true", dest="molprobity_full", default=False,
               help="Update the large MolProbity API tables.")
opt.add_option("--timedomain", action="store_true", dest="timedomain", default=False,
               help="Update the timedomain tables.")
opt.add_option("--uniprot", action="store_true", dest="uniprot", default=False, help="Update the UniProt tables.")
opt.add_option("--xml", action="store_true", dest="xml", default=False, help="Update the XML file for BMRB entries.")
opt.add_option("--inext", action="store_true", dest="inext", default=False, help="Update the iNext tables.")
opt.add_option("--sql", action="store_true", dest="sql", default=False,
               help="Run the SQL commands to prepare the correct indexes on the DB.")
opt.add_option("--sql-host", action="store", dest='sql_host', default=configuration['postgres']['host'],
               help="Host to run the SQL updater on.")
opt.add_option("--sql-database", action="store", dest='sql_database', default=configuration['postgres']['database'],
               help="Database to run the SQL updater on.")
opt.add_option("--sql-user", action="store", dest='sql_user', default=configuration['postgres']['reload_user'],
               help="User to run the SQL updater as.")
opt.add_option("--sql-port", action="store", dest='sql_port', default=configuration['postgres']['port'],
               help="Port to connect to Postgres on.")
opt.add_option("--all-entries", action="store_true", dest="all", default=False,
               help="Update all the databases, and run all reloaders. Equivalent to: --metabolomics --macromolecules "
                    "--chemcomps --molprobity-visualization --molprobity-full --uniprot --sql --timedomain")
opt.add_option("--redis-db", action="store", dest="redis_db", default=configuration['redis']['db'],
               help="The Redis DB to use. 0 is master.")
opt.add_option("--redis-host", action="store", dest="redis_host", default=None,
               help="The Redis host to use, if not using sentinels.")
opt.add_option("--redis-port", action="store", dest="redis_port", default=None,
               help="The port to try to connect to Redis on.")
opt.add_option("--flush", action="store_true", dest="flush", default=False,
               help="Flush all keys in the DB prior to reloading. This will interrupt service until the DB is rebuilt! "
                    "(So only use it on the staging DB.)")
opt.add_option("--verbose", action="store_true", dest="verbose", default=False, help="Be verbose")
# Parse the command line input
(options, cmd_input) = opt.parse_args()

# Set all of the config options from the command line - way easier than trying to pass them through everywhere
configuration['postgres']['reload_user'] = options.sql_user
configuration['postgres']['host'] = options.sql_host
configuration['postgres']['database'] = options.sql_database
configuration['postgres']['port'] = options.sql_port
configuration['redis']['db'] = options.redis_db
if options.redis_host:
    configuration['redis']['sentinels'][0][0] = options.redis_host
if options.redis_port:
    configuration['redis']['sentinels'][0][1] = options.redis_port

logging.basicConfig()
logger = logging.getLogger()
if options.verbose:
    logger.setLevel(logging.DEBUG)
else:
    logger.setLevel(logging.WARNING)

# Make sure they specify a DB
if not (options.metabolomics or options.macromolecules or options.chemcomps or options.molprobity_visualization
        or options.molprobity_full or options.uniprot or options.xml or options.inext or options.sql or
        options.timedomain or options.all):
    logging.exception("You must specify at least one of the reloaders.")
    sys.exit(1)

# Update the values if all is presented
if options.all:
    options.metabolomics = True
    options.macromolecules = True
    options.chemcomps = True
    options.molprobity_visualization = True
    options.molprobity_full = True
    options.uniprot = True
    options.sql = True
    options.timedomain = True
    options.xml = True
    #options.inext = True

if options.timedomain:
    logger.info('Doing timedomain data reload...')
    timedomain()
    logger.info('Finished timedomain data reload...')

if options.xml:
    logger.info('Doing XML generation...')
    xml(configuration['internal_data_directory'])
    logger.info('Finished XML reload...')

if options.uniprot:
    logger.info('Doing UniProt reload...')
    uniprot()
    logger.info('Finished UniProt reload...')

if options.inext:
    logger.info('Doing iNext reload...')
    inext()
    logger.info('Finished iNext reload...')

if options.sql:
    logger.info('Doing SQL initialization...')
    if sql_initialize(host=options.sql_host, database=options.sql_database, user=options.sql_user):
        logger.info('Finished SQL initialization...')
    else:
        logger.exception('SQL reloading exited with exception.')

# Load the metabolomics data
if options.metabolomics:
    logger.info('Calculating metabolomics entries to process...')
    with PostgresConnection() as cur:
        cur.execute('SELECT DISTINCT "Entry_ID" FROM metabolomics."Release" ORDER BY "Entry_ID"')
        entries = sorted([x['Entry_ID'] for x in cur.fetchall()])

    if len(entries) < 1000:
        raise ValueError("Refusing to continue, the DB appears corrupted.")

    substitution_count = configuration['metabolomics_entry_directory'].count("%s")
    for entry in entries:
        entry_dir = os.path.join(configuration['metabolomics_entry_directory'] % ((entry,) * substitution_count),
                                 f"{entry}.str")
        to_process['metabolomics'].append((entry, entry_dir))
    logger.info('Finished calculating metabolomics entries to process.')

# Get the released entries from ETS
if options.macromolecules:
    logger.info('Calculating macromolecule entries to process...')
    with PostgresConnection() as cur:
        cur.execute('SELECT DISTINCT "ID" FROM macromolecules."Entry" ORDER BY "ID";')
        valid_ids = sorted([x['ID'] for x in cur.fetchall()])

    if len(valid_ids) < 10000:
        raise ValueError("Refusing to continue, the DB appears corrupted.")

    substitution_count = configuration['macromolecule_entry_directory'].count("%s")

    # Load the normal data
    for entry_id in valid_ids:
        entry_dir = os.path.join(configuration['macromolecule_entry_directory'] % ((entry_id,) * substitution_count),
                                 f"bmr{entry_id}_3.str")
        to_process['macromolecules'].append([str(entry_id), entry_dir])
    logger.info('Finished calculating macromolecule entries to process.')

# Load the chemcomps
if options.chemcomps:
    logger.info('Calculating chemcomp entries to process...')
    with PostgresConnection() as cur:
        cur.execute('SELECT DISTINCT "BMRB_code" FROM chemcomps."Entity" ORDER BY "BMRB_code"')
        comp_ids = sorted([x['BMRB_code'] for x in cur.fetchall()])
    if len(comp_ids) < 1000:
        raise ValueError("Refusing to continue, the DB appears corrupted.")
    chemcomps = ["chemcomp_" + x for x in comp_ids]
    to_process['chemcomps'].extend([[x, None] for x in chemcomps])
    logger.info('Finished calculating chemcomp entries to process.')

# Generate the flat list of entries to process
to_process['combined'] = (to_process['chemcomps'] + to_process['macromolecules'] + to_process['metabolomics'])

# If specified, flush the DB
if options.flush:
    logging.info("Flushing the DB.")
    with RedisConnection() as r:
        r.flushdb()

if options.chemcomps or options.macromolecules or options.metabolomics:

    logger.info('Updating entries in Redis...')

    with multiprocessing.Pool() as pool:
        for res in pool.map(one_entry, to_process['combined']):
            add_to_loaded(res)

    with RedisConnection() as r_conn:
        # Use a Redis list so other applications can read the list of entries
        if options.metabolomics:
            make_entry_list('metabolomics')
        if options.macromolecules:
            make_entry_list('macromolecules')
        if options.chemcomps:
            make_entry_list('chemcomps')

        # Make the full list from the existing lists regardless of update type
        loaded['combined'] = (r_conn.lrange('metabolomics:entry_list', 0, -1) +
                              r_conn.lrange('macromolecules:entry_list', 0, -1) +
                              r_conn.lrange('chemcomps:entry_list', 0, -1))
        make_entry_list('combined')

        if r_conn.info()['rdb_bgsave_in_progress'] == 1:
            logging.info('Redis save already in progress, not asking for one...')
        else:
            # Trigger a manual save to disk after reload
            r_conn.bgsave()
    logger.info('Finished updating list of entries present in Redis...')

# The quicker molprobity code to generate the data for the molprobity visualizer
if options.molprobity_visualization:
    logger.info('Doing MolProbity visualization reload...')
    molprobity_visualizations()
    logger.info('Finished MolProbity visualization reload...')

# Full MolProbity should run last since it takes so long
if options.molprobity_full:
    logger.info('Doing full MolProbity reload...')
    molprobity_full()
    logger.info('Finished full MolProbity reload...')
