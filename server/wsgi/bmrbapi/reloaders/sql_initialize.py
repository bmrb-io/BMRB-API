import logging
import os
import subprocess

from bmrbapi.utils.configuration import configuration


def sql_initialize(host=configuration['postgres']['host'],
                   database=configuration['postgres']['database'],
                   user=configuration['postgres']['reload_user']) -> bool:
    """ Prepare the DB for querying. """

    initialize_file = os.path.join(os.path.dirname(os.path.realpath(__file__)), "sql", "initialize.sql")

    # Rather than connect directly, we use the psql client. This is because the \copy commands will not work
    #  in psycopg2 without doing it this way
    proc = subprocess.Popen(['/usr/bin/psql', '-d', database, '-U', user, '-h', host, '-f', initialize_file,
                             '-v', 'ON_ERROR_STOP=1'],
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    stdout, stderr = proc.communicate()
    if proc.returncode != 0 and stderr:
        logging.warning('SQL reload experienced the following errors:\n%s' % stderr.decode())
    return proc.returncode == 0
