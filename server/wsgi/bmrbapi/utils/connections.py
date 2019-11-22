import psycopg2

from bmrbapi import RequestException
from bmrbapi.utils.configuration import configuration


class PostgresConnection:
    """ Makes it more convenient to query postgres. It implements a context manager to ensure that the connection
    is closed."""

    def __init__(self,
                 host=configuration['postgres']['host'],
                 user=configuration['postgres']['user'],
                 database=configuration['postgres']['database'],
                 port=configuration['postgres']['port'],
                 cursor_factory=psycopg2.extras.DictCursor,
                 schema=None):
        self._host = host
        self._user = user
        self._database = database
        self._port = port
        self._cursor_factory = cursor_factory

        # Check the schema
        if schema:
            if schema == "combined":
                raise RequestException("Combined database not implemented yet.")
            if schema not in ["metabolomics", "macromolecules", "chemcomps"]:
                raise RequestException("Invalid database: %s." % schema)
        self._schema = schema

    def __enter__(self):
        self._conn = psycopg2.connect(host=self._host, user=self._user, database=self._database,
                                      port=self._port, cursor_factory=self._cursor_factory)
        cursor = self._conn.cursor()
        if self._schema:
            cursor.execute('SET search_path=public,%s;', [self._schema])
        return cursor

    def __exit__(self, exc_type, exc_val, exc_tb):
        self._conn.close()

    def commit(self):
        self._conn.commit()