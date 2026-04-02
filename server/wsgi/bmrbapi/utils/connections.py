import logging
from typing import Optional

import psycopg
import redis
from psycopg import sql
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool
from redis.sentinel import Sentinel

from bmrbapi.exceptions import RequestException, ServerException
from bmrbapi.utils.configuration import configuration

logger = logging.getLogger(__name__)

# Module-level connection pools, created lazily on first use
_pools: dict[str, ConnectionPool] = {}


def _get_pool(ets: bool = False, write_access: bool = False) -> ConnectionPool:
    """Get or create a connection pool for the given connection type."""

    key = 'ets' if ets else ('write' if write_access else 'read')
    if key not in _pools:
        if ets:
            conninfo = psycopg.conninfo.make_conninfo(
                host=configuration['ets']['host'],
                user=configuration['ets']['user'],
                dbname=configuration['ets']['database'],
                port=configuration['ets']['port'],
            )
        else:
            user = (configuration['postgres']['reload_user'] if write_access
                    else configuration['postgres']['user'])
            conninfo = psycopg.conninfo.make_conninfo(
                host=configuration['postgres']['host'],
                user=user,
                dbname=configuration['postgres']['database'],
                port=configuration['postgres']['port'],
            )
        _pools[key] = ConnectionPool(conninfo, min_size=2, max_size=20, open=True)
        logger.info("Created connection pool '%s' (min=2, max=20)", key)
    return _pools[key]


class DictRow(list):
    """A row class that supports both index and key-based access, matching psycopg2's DictRow behavior.

    This allows code to use both row[0] and row['column_name'] interchangeably,
    and serializes as a JSON array (since it inherits from list)."""
    __slots__ = ('_index',)

    def __init__(self, keys, values):
        super().__init__(values)
        self._index = {key: i for i, key in enumerate(keys)}

    def __getitem__(self, key):
        if isinstance(key, str):
            return super().__getitem__(self._index[key])
        return super().__getitem__(key)

    def __contains__(self, key):
        if isinstance(key, str):
            return key in self._index
        return super().__contains__(key)

    def keys(self):
        return self._index.keys()

    def values(self):
        return [super(DictRow, self).__getitem__(i) for i in range(len(self))]

    def items(self):
        return [(key, self[key]) for key in self._index]

    def get(self, key, default=None):
        try:
            return self[key]
        except (KeyError, IndexError):
            return default


def compat_row_factory(cursor):
    """Row factory that returns DictRow objects with both index and key access."""
    desc = cursor.description
    if desc is None:
        return lambda values: DictRow((), values)
    columns = tuple(d.name for d in desc)
    return lambda values: DictRow(columns, values)


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
        self._real_dict = real_dict_cursor
        self._conn: Optional[psycopg.Connection] = None
        self._pool: Optional[ConnectionPool] = None

        # Check the schema
        if schema:
            if schema == "combined":
                raise RequestException("Combined database not implemented yet.")
            if schema not in ["metabolomics", "macromolecules", "chemcomps"]:
                raise RequestException("Invalid database: %s." % schema)
        self._schema = schema

    def __enter__(self) -> psycopg.Cursor:

        row_factory = dict_row if self._real_dict else compat_row_factory

        self._pool = _get_pool(ets=self._ets, write_access=self._reload)
        self._conn = self._pool.getconn()
        self._conn.row_factory = row_factory

        cursor = self._conn.cursor()
        if self._schema:
            cursor.execute(sql.SQL('SET search_path=public,{}').format(sql.Identifier(self._schema)))
        return cursor

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self._conn and self._pool:
            # Reset search_path before returning to pool so the next user gets a clean connection
            if self._schema:
                try:
                    self._conn.execute("RESET search_path")
                except Exception:
                    pass
            # Rollback any open transaction before returning to pool to avoid
            # "rolling back returned connection" warnings from psycopg_pool
            try:
                self._conn.rollback()
            except Exception:
                pass
            self._pool.putconn(self._conn)
            self._conn = None

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
