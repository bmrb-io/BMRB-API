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
_redis: Optional[redis.StrictRedis] = None


def reset_pools():
    """Close and discard all connection pools.

    Must be called in forked child processes (e.g. via multiprocessing.Pool initializer)
    so that each worker creates its own fresh connections instead of inheriting
    the parent's SSL-tainted file descriptors."""
    global _redis

    for pool in _pools.values():
        try:
            pool.close()
        except Exception:
            pass
    _pools.clear()
    _redis = None


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


def _get_redis() -> redis.StrictRedis:
    """Get or create the Redis client. It keeps its own pool of connections."""

    global _redis
    if _redis is None:
        password = configuration['redis']['password'] if configuration['redis']['password'] else None
        sentinels = configuration['redis']['sentinels']

        # If there is only one sentinel, just treat that as the Redis instance itself, and not a sentinel
        if len(sentinels) == 1:
            _redis = redis.StrictRedis(host=sentinels[0][0], port=sentinels[0][1],
                                       db=configuration['redis']['db'], password=password)
        else:
            # The sentinels are asked for the master whenever a connection is made, so failover is followed
            _redis = Sentinel(sentinels, socket_timeout=0.5).master_for(configuration['redis']['master_name'],
                                                                         db=configuration['redis']['db'],
                                                                         password=password)
    return _redis


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
    """ Gives access to the master redis instance, using a context manager.

    The client (and its connection pool) is created once per process and reused, so
    connections stay open between requests. If only one "sentinel" is defined, then
    just connect directly to that machine rather than checking the sentinels. """

    def __enter__(self) -> redis.StrictRedis:
        return _get_redis()

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type is redis.sentinel.MasterNotFoundError:
            raise ServerException('Could not determine Redis host. Sentinels offline?') from exc_val
