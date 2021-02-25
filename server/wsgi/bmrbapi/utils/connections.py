from typing import Union

import psycopg2
import psycopg2.extras
import redis
from redis.sentinel import Sentinel

from bmrbapi.exceptions import RequestException, ServerException
from bmrbapi.utils.configuration import configuration


class PostgresConnection:
    """ Makes it more convenient to query postgres. It implements a context manager to ensure that the connection
    is closed.

    Specify write_access=True to use the reload user account with write access. Do not use this whenever user input
    is involved!
    Specify ets=True to connect to the ETS database.
    Specify a schema to set it as the default search path."""

    def __init__(self, write_access: bool = False, ets: bool = False, schema: str = None,
                 real_dict_cursor: bool = False):

        self._ets = ets
        self._reload = write_access
        self._cursor_type = psycopg2.extras.DictCursor
        if real_dict_cursor:
            self._cursor_type = psycopg2.extras.RealDictCursor

        # Check the schema
        if schema:
            if schema == "combined":
                raise RequestException("Combined database not implemented yet.")
            if schema not in ["metabolomics", "macromolecules", "chemcomps"]:
                raise RequestException("Invalid database: %s." % schema)
        self._schema = schema

    def __enter__(self) -> Union[psycopg2.extras.DictCursor, psycopg2.extras.RealDictCursor]:

        if self._ets:
            self._conn = psycopg2.connect(host=configuration['ets']['host'],
                                          user=configuration['ets']['user'],
                                          database=configuration['ets']['database'],
                                          port=configuration['ets']['port'],
                                          cursor_factory=self._cursor_type)
        else:
            user = configuration['postgres']['user'] if not self._reload else configuration['postgres']['reload_user']
            self._conn = psycopg2.connect(host=configuration['postgres']['host'],
                                          user=user,
                                          database=configuration['postgres']['database'],
                                          port=configuration['postgres']['port'],
                                          cursor_factory=self._cursor_type)
        cursor = self._conn.cursor()
        if self._schema:
            cursor.execute('SET search_path=public,%s;', [self._schema])
        return cursor

    def __exit__(self, exc_type, exc_val, exc_tb):
        self._conn.close()

    def commit(self):
        self._conn.commit()

    def rollback(self):
        self._conn.rollback()


class RedisConnection:
    """ Figures out where the master redis instance is (and other parameters
    needed to connect like which database to use), and opens a connection
    to it. It passes back that connection object, using a context manager
    to clean up after use.

    If only one "sentinel" is defined, then just connect directly to that machine rather than checking the sentinels. """

    def __init__(self):
        """ Creates a connection instance. Optionally specify a non-default db. """

        # If there is only one sentinel, just treat that as the Redis instance itself, and not a sentinel
        if len(configuration['redis']['sentinels']) == 1:
            self._redis_host = configuration['redis']['sentinels'][0][0]
            self._redis_port = configuration['redis']['sentinels'][0][1]
        else:
            # Connect to the sentinels to determine the master
            try:
                sentinel = Sentinel(configuration['redis']['sentinels'], socket_timeout=0.5)
                self._redis_host, self._redis_port = sentinel.discover_master(configuration['redis']['master_name'])

            # Raise an exception if we cannot connect to the database server
            except redis.sentinel.MasterNotFoundError:
                raise ServerException('Could not determine Redis host. Sentinels offline?')

    def __enter__(self) -> redis.StrictRedis:
        try:
            password = configuration['redis']['password'] if configuration['redis']['password'] else None
            self._redis_con = redis.StrictRedis(host=self._redis_host,
                                                port=self._redis_port,
                                                db=configuration['redis']['db'],
                                                password=password)
        except redis.exceptions.ConnectionError:
            raise ServerException('Could not connect to Redis server.')
        return self._redis_con

    def __exit__(self, exc_type, exc_val, exc_tb):
        self._redis_con.close()
