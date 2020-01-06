import os

from bmrbapi.utils.configuration import configuration
from bmrbapi.utils.connections import PostgresConnection


def initialize() -> None:
    """ Prepare the DB for querying. """

    psql = PostgresConnection(user=configuration['postgres']['reload_user'])
    with psql as cur:
        sql_file = os.path.join(os.path.dirname(os.path.realpath(__file__)), "sql", "initialize.sql")
        cur.execute(open(sql_file, "r").read())
        psql.commit()
