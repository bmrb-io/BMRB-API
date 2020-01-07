import logging
import os
import subprocess
from tempfile import NamedTemporaryFile

from bmrbapi.utils.configuration import configuration
from bmrbapi.utils.connections import PostgresConnection


def molprobity() -> bool:
    """ This takes a long time. """

    with NamedTemporaryFile(delete=False) as tmp:
        cmd = subprocess.Popen('LC_ALL=C find %s/residue_files/combined/ -name \\*.csv -print0 | xargs -0 cat | '
                               'sort -u -i - > %s' %
                               (configuration['molprobity_directory'], tmp.name), shell=True, stderr=subprocess.PIPE)
        stderr = cmd.communicate()
        if stderr:
            logging.debug('Errors when sorting:\n%s', stderr)
            return False

        psql = PostgresConnection(user=configuration['postgres']['reload_user'])
        with psql as cur:
            sql_file = os.path.join(os.path.dirname(os.path.realpath(__file__)), "sql", 'molprobity.sql')
            raw_sql = open(sql_file, 'r').read()
            sql_query = raw_sql % (configuration['molprobity_directory'], configuration['molprobity_directory'],
                                   configuration['molprobity_directory'], tmp.name)
            cur.execute(sql_query)
            psql.commit()

    return True
