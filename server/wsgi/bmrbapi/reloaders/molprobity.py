import logging
import os
import subprocess

from bmrbapi.utils.configuration import configuration
from bmrbapi.utils.connections import PostgresConnection


def molprobity() -> bool:
    """ This takes a long time. """

    cmd = subprocess.Popen('LC_ALL=C find %s/residue_files/combined/ -name \\*.csv -print0 | xargs -0 cat | '
                           'sort -u -i -S2G --compress-program gzip -' %
                           configuration['molprobity_directory'], shell=True, stderr=subprocess.PIPE,
                           stdout=subprocess.PIPE)

    psql = PostgresConnection(user=configuration['postgres']['reload_user'])
    with psql as cur:
        # Do the oneline files and prepare for the residue file
        sql_path = os.path.join(os.path.dirname(os.path.realpath(__file__)), "sql", 'molprobity_one.sql')
        with open(sql_path, 'r') as sql_file:
            cur.execute(sql_file.read())

        # Insert the data from the files
        nobuild_location = os.path.join(configuration['molprobity_directory'],
                                        'oneline_files/combined/allonelinenobuild.out.csv')
        build_location = os.path.join(configuration['molprobity_directory'],
                                      'oneline_files/combined/allonelinebuild.out.csv')
        orig_location = os.path.join(configuration['molprobity_directory'],
                                     'oneline_files/combined/allonelineorig.out.csv')
        with open(nobuild_location, 'r') as nobuild_file:
            cur.copy_from(nobuild_file, 'tmp_table', sep=':', null='')
        with open(build_location, 'r') as build_file:
            cur.copy_from(build_file, 'tmp_table', sep=':', null='')
        with open(orig_location, 'r') as orig_file:
            cur.copy_from(orig_file, 'tmp_table', sep=':', null='')

        # Do the residue file
        cur.copy_expert("copy molprobity.residue_tmp FROM STDIN DELIMITER ':' CSV;", cmd.stdout)

        # Check stderr
        stderr = cmd.stderr.read()
        if stderr:
            logging.debug('Errors when sorting:\n%s', stderr)
            return False

        # Finalize
        sql_path = os.path.join(os.path.dirname(os.path.realpath(__file__)), "sql", 'molprobity_two.sql')
        with open(sql_path, 'r') as sql_file:
            cur.execute(sql_file.read())

        psql.commit()

    return True
