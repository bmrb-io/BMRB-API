import logging
import os
import subprocess
from tempfile import NamedTemporaryFile

from bmrbapi.utils.configuration import configuration
from bmrbapi.utils.connections import PostgresConnection


def molprobity() -> None:
    """ This takes a long time. """

    with NamedTemporaryFile(delete=False) as tmp:
        cmd = subprocess.Popen('LC_ALL=C sort -u -i /websites/extras/files/pdb/molprobity/residue_files/everything.csv'
                               ' > %s' % tmp.name, shell=True, stderr=subprocess.PIPE)
        stderr = cmd.communicate()
        if stderr:
            logging.debug('Errors when sorting:\n%s', stderr)
            return

        psql = PostgresConnection(user=configuration['postgres']['reload_user'])
        with psql as cur:
            sql_file = os.path.join(os.path.dirname(os.path.realpath(__file__)), "sql", 'molprobity.sql')
            raw_sql = open(sql_file, 'r').read()
            sql_query = raw_sql % (configuration['molprobity_directory'], configuration['molprobity_directory'],
                                   configuration['molprobity_directory'], configuration['molprobity_directory'])
            cur.execute(sql_query)
            psql.commit()
