import sqlite3

from bmrbapi.utils.connections import PostgresConnection


def csrosetta(csrosetta_sqlite_file: str) -> None:
    """Creates the CS-Rosetta links table."""

    with sqlite3.connect(csrosetta_sqlite_file) as sqlite3_conn, sqlite3_conn as c:
        entries = c.execute('''
SELECT key, bmrbid, rosetta_version, csrosetta_version, rmsd_lowest
  FROM entries;''').fetchall()

        psql = PostgresConnection()
        with psql as cur:
            cur.execute('DROP TABLE IF EXISTS web.bmrb_csrosetta_entries')
            cur.execute('''
CREATE TABLE web.bmrb_csrosetta_entries (
 key varchar(13) PRIMARY KEY,
 bmrbid integer,
 rosetta_version
 varchar(5),
 csrosetta_version varchar(5),
 rmsd_lowest float)''')

            cur.executemany('''
INSERT INTO web.bmrb_csrosetta_entries(key, bmrbid, rosetta_version, csrosetta_version, rmsd_lowest)
VALUES (%s, %s, %s, %s, %s)''', entries)

            psql.commit()
