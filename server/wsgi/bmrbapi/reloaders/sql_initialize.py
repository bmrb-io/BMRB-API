import logging
import os
import subprocess
from tempfile import NamedTemporaryFile

from bmrbapi.utils.configuration import configuration


def sql_initialize(host=configuration['postgres']['host'],
                   database=configuration['postgres']['database'],
                   user=configuration['postgres']['reload_user']) -> None:
    """ Prepare the DB for querying. """

    with NamedTemporaryFile('w', delete=False) as temp:
        '/website/www/ftp/pub/bmrb/nmr_pdb_integrated_data/adit_nmr_matched_pdb_bmrb_entry_ids.csv'
        with open(os.path.join(os.path.dirname(os.path.realpath(__file__)), "sql", "initialize.sql"), 'r') as sql_file:
            link_file_path = os.path.join(configuration['nmr_integrated_data_directory'],
                                          'adit_nmr_matched_pdb_bmrb_entry_ids.csv')
            sql_data = sql_file.read().replace('{{nmr_integrated_data_directory}}', link_file_path)
            temp.write(sql_data)
            temp.flush()

        # Rather than connect directly, we use the psql client. This is because the \copy commands will not work
        #  in psycopg2 without
        proc = subprocess.Popen(['/usr/bin/psql', '-d', database, '-U', user, '-h', host, '-f', temp.name,
                                 '-v', 'ON_ERROR_STOP=1'],
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        stdout, stderr = proc.communicate()
        if proc.returncode != 0 and stderr:
            logging.warning('SQL reload experienced the following errors:\n%s' % stderr.decode())
        return proc.returncode == 0
