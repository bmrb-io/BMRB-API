import sqlite3

from psycopg2.extras import execute_values

from bmrbapi.utils.connections import PostgresConnection


def csrosetta(csrosetta_sqlite_file: str) -> None:
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
