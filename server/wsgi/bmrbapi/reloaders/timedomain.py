import logging
import os

from psycopg2.extras import execute_values

from bmrbapi.utils.configuration import configuration
from bmrbapi.utils.connections import PostgresConnection, RedisConnection


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
        substitution_count = configuration['macromolecule_entry_directory'].count("%s")

        with RedisConnection() as r:
            all_entries = [_[0] for _ in r.lrange('macromolecules:entry_list', 0, -1)]
        for entry_id in all_entries:
            td_dir = os.path.join(
                configuration['macromolecule_entry_directory'] % ((entry_id,) * substitution_count),
                'timedomain_data')
            if os.path.exists(td_dir):
                logging.debug(f'Processing TD directory: {td_dir}')
                yield entry_id, get_dir_size(td_dir), get_data_sets(td_dir)
            else:
                logging.warning(f"Entry directory that was supposed to exist did not: {td_dir}")

    psql = PostgresConnection(write_access=True)
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
DROP TABLE IF EXISTS web.timedomain_data_old;
GRANT USAGE ON schema web TO PUBLIC;
GRANT SELECT ON ALL TABLES IN schema web TO PUBLIC;
ALTER DEFAULT PRIVILEGES IN schema web GRANT SELECT ON TABLES TO PUBLIC;
GRANT ALL PRIVILEGES ON TABLE web.timedomain_data to web;
GRANT ALL PRIVILEGES ON TABLE web.timedomain_data to bmrb;
''')
        psql.commit()
