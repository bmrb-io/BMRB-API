import os
import sqlite3

from psycopg2.extras import execute_values

from bmrbapi import PostgresConnection, configuration


def do_sql_mods(sql_file: str = None) -> None:
    """ Make sure functions we need are saved in the DB. """

    psql = PostgresConnection(user=configuration['postgres']['reload_user'])
    with psql as cur:
        if sql_file is None:
            sql_file = os.path.join(os.path.dirname(os.path.realpath(__file__)), "sql", "initialize.sql")
        else:
            sql_file = os.path.join(os.path.dirname(os.path.realpath(__file__)), "sql", sql_file)

        cur.execute(open(sql_file, "r").read())
        psql.commit()


def create_timedomain_table() -> None:
    """Creates the time domain links table."""

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

    def td_data_getter():
        td_dir = configuration['timedomain_directory']
        for x in os.listdir(td_dir):
            entry_id = int("".join([_ for _ in x if _.isdigit()]))
            yield entry_id, get_dir_size(os.path.join(td_dir, x)), get_data_sets(os.path.join(td_dir, x))

    psql = PostgresConnection(user=configuration["postgres"]["reload_user"])
    with psql as cur:
        cur.execute('''
CREATE TABLE IF NOT EXISTS web.timedomain_data_tmp (
 bmrbid text PRIMARY KEY,
 size numeric,
 sets numeric);''')

        execute_values(cur, '''INSERT INTO web.timedomain_data_tmp(bmrbid, size, sets) VALUES %s;''', td_data_getter())

        cur.execute('''
ALTER TABLE IF EXISTS web.timedomain_data RENAME TO timedomain_data_old;
ALTER TABLE web.timedomain_data_tmp RENAME TO timedomain_data;
DROP TABLE IF EXISTS web.timedomain_data_old;''')
        psql.commit()


def create_csrosetta_table(csrosetta_sqlite_file: str) -> None:
    """Creates the CS-Rosetta links table."""

    with sqlite3.connect(csrosetta_sqlite_file) as sqlite3_conn, sqlite3_conn as c:
        entries = c.execute('''
SELECT key, bmrbid, rosetta_version, csrosetta_version, rmsd_lowest
  FROM entries;''').fetchall()

        psql = PostgresConnection()
        with psql as cur:
            cur.execute('''
DROP TABLE IF EXISTS web.bmrb_csrosetta_entries;
CREATE TABLE web.bmrb_csrosetta_entries (
 key varchar(13) PRIMARY KEY,
 bmrbid integer,
 rosetta_version
 varchar(5),
 csrosetta_version varchar(5),
 rmsd_lowest float);''')

            execute_values(cur, '''
INSERT INTO web.bmrb_csrosetta_entries(key, bmrbid, rosetta_version, csrosetta_version, rmsd_lowest)
VALUES %s;''', entries)

            psql.commit()