import os

from psycopg2.extras import execute_values

from bmrbapi.utils.configuration import configuration
from bmrbapi.utils.connections import PostgresConnection


def timedomain() -> None:
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