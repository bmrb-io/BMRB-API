#!/usr/bin/env python

"""Creates the time domain links table."""

import os
import optparse

import psycopg2
from psycopg2.extras import execute_values

opt = optparse.OptionParser(usage="usage: %prog", version="1.0",
                            description="Reload the time domain data table.")
opt.add_option("--host", action="store", dest="host",
               default="manta", help="Hostname of the machine with the DB.")
opt.add_option("--port", action="store", dest="port",
               default="5432", help="Port of the machine with the DB.")
opt.add_option("--database", action="store", dest="db",
               default="bmrbeverything", help="The name of the database that the data resides in.")
opt.add_option("--user", action="store", dest="user",
               default="bmrb", help="The user to use to connect to the database.")
opt.add_option("--timedomain-folder", action="store", dest="td_folder",
               default='/website/ftp/pub/bmrb/timedomain/',
               help="The location of the time domain data.")
# Parse the command line input
(options, cmd_input) = opt.parse_args()


def get_dir_size(start_path='.'):
    total_size = 0
    for dir_path, dir_names, file_names in os.walk(start_path):
        for f in file_names:
            fp = os.path.join(dir_path, f)
            total_size += os.path.getsize(fp)
    return total_size


def get_data_sets(path):
    sets = 0
    last_set = ""
    for f in os.listdir(path):
        if os.path.isdir(os.path.join(path, f)):
            sets += 1
            last_set = os.path.join(path, f)
    if sets == 1:
        child_sets = get_data_sets(last_set)
        if child_sets > 1:
            return child_sets
    return sets


conn = psycopg2.connect(user=options.user, host=options.host, database=options.db,
                        port=options.port)
cur = conn.cursor()

cur.execute('''
CREATE TABLE IF NOT EXISTS web.timedomain_data_tmp (
bmrbid text PRIMARY KEY,
size numeric,
sets numeric);''')


def td_data_getter():
    td_dir = options.td_folder
    for x in os.listdir(td_dir):
        entry_id = int("".join([_ for _ in x if _.isdigit()]))
        yield (entry_id, get_dir_size(os.path.join(td_dir, x)), get_data_sets(os.path.join(td_dir, x)))


execute_values(cur, '''INSERT INTO web.timedomain_data_tmp(bmrbid, size, sets) VALUES %s;''', td_data_getter())

cur.execute('''
ALTER TABLE IF EXISTS web.timedomain_data RENAME TO timedomain_data_old;
ALTER TABLE web.timedomain_data_tmp RENAME TO timedomain_data;
DROP TABLE IF EXISTS web.timedomain_data_old;''')
conn.commit()
