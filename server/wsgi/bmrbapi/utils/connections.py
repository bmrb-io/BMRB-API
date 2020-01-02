import psycopg2
import psycopg2.extras
import redis
from redis.sentinel import Sentinel

from bmrbapi.exceptions import RequestException, ServerException
from bmrbapi.utils.configuration import configuration


class PostgresConnection:
    """ Makes it more convenient to query postgres. It implements a context manager to ensure that the connection
    is closed."""

    def __init__(self,
                 host=configuration['postgres']['host'],
                 user=configuration['postgres']['user'],
                 database=configuration['postgres']['database'],
                 port=configuration['postgres']['port'],
                 schema=None):
        self._host = host
        self._user = user
        self._database = database
        self._port = port

        # Check the schema
        if schema:
            if schema == "combined":
                raise RequestException("Combined database not implemented yet.")
            if schema not in ["metabolomics", "macromolecules", "chemcomps"]:
                raise RequestException("Invalid database: %s." % schema)
        self._schema = schema

    def __enter__(self) -> psycopg2.extras.DictCursor:
        self._conn = psycopg2.connect(host=self._host, user=self._user, database=self._database,
                                      port=self._port, cursor_factory=psycopg2.extras.DictCursor)
        cursor = self._conn.cursor()
        if self._schema:
            cursor.execute('SET search_path=public,%s;', [self._schema])
        return cursor

    def __exit__(self, exc_type, exc_val, exc_tb):
        self._conn.close()

    def commit(self):
        self._conn.commit()


def get_redis_connection(db: int = None):
    """ Figures out where the master redis instance is (and other parameters
    needed to connect like which database to use), and opens a connection
    to it. It passes back that connection object."""

    with RedisConnection(db=db) as r:
        return r


class RedisConnection:
    """ Figures out where the master redis instance is (and other parameters
    needed to connect like which database to use), and opens a connection
    to it. It passes back that connection object, using a context manager
    to clean up after use."""

    def __init__(self, db: int = None):
        """ Creates a connection instance. Optionally specify a non-default db. """

        # Connect to redis
        try:
            # Figure out where we should connect
            sentinel = Sentinel(configuration['redis']['sentinels'], socket_timeout=0.5)
            self._redis_host, self._redis_port = sentinel.discover_master(configuration['redis']['master_name'])

            # If they didn't specify a DB then use the configuration default
            if db is None:
                # If in debug, use debug database
                if configuration['debug']:
                    db = 1
                else:
                    db = configuration['redis']['db']

            self._db = db

        # Raise an exception if we cannot connect to the database server
        except redis.sentinel.MasterNotFoundError:
            raise ServerException('Could not determine Redis host. Sentinels offline?')

    def __enter__(self) -> redis.StrictRedis:
        try:
            self._redis_con = redis.StrictRedis(host=self._redis_host,
                                                port=self._redis_port,
                                                db=self._db,
                                                password=configuration['redis']['password'])
        except redis.exceptions.ConnectionError:
            raise ServerException('Could not connect to Redis server.')
        return self._redis_con

    def __exit__(self, exc_type, exc_val, exc_tb):
        self._redis_con.close()
