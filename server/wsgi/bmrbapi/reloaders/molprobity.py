import json
import logging
import os
import subprocess
from io import StringIO
from subprocess import Popen, PIPE
from urllib.request import urlopen

from bmrbapi.utils.configuration import configuration
from bmrbapi.utils.connections import PostgresConnection


def molprobity_visualizations(host=configuration['postgres']['host'],
                              database=configuration['postgres']['database'],
                              user=configuration['postgres']['reload_user'],
                              resolution: int = 3000):
    csv_location = configuration['molprobity_directory'] + '/oneline_files/'

    conn = PostgresConnection(user=user, host=host, database=database)
    with conn as cur:

        script_dir = os.path.dirname(os.path.realpath(__file__))

        # The various field possibilities
        data_fields = ['cbeta_outlier', 'rota_less1pct', 'ramaoutlier', 'pct_badbonds', 'pct_badangles', 'clashscore',
                       'numpperp_outlier', 'numsuite_outlier', 'molprobityscore']
        experiment_types = ['nmr', 'notnmr', 'combined']
        hydrogen_flip_states = ['build', 'nobuild', 'orig']
        backbone_trim_states = ['core', 'full']

        # Prepare the averages table
        cur.execute("DROP TABLE IF EXISTS molprobity.averages_working;")
        averages_columns = "".join([", %s FLOAT, %s_abs FLOAT, %s_raw FLOAT" % (x, x, x) for x in data_fields])
        cur.execute("""
CREATE TABLE molprobity.averages_working(experiment_type TEXT,
                                         hydrogen_flip_state TEXT,
                                         backbone_trim_state TEXT,
                                         macromolecule_type TEXT,
                                         pdb TEXT,
                                         model INTEGER %s);""" % averages_columns)
        cur.execute("DROP TABLE IF EXISTS molprobity.distributions_working;")
        distribution_columns = "".join([", %s_abs NUMERIC(10,4), %s_count INTEGER" % (x, x) for x in data_fields])
        cur.execute("""
CREATE TABLE molprobity.distributions_working(experiment_type TEXT,
                                              hydrogen_flip_state TEXT,
                                              backbone_trim_state TEXT %s);""" % distribution_columns)

        # Import the data from files
        for each_folder in os.listdir(csv_location):
            if os.path.isdir(os.path.join(csv_location, each_folder)):
                for each_file in os.listdir(os.path.join(csv_location, each_folder)):
                    hydrogen_flip_state = each_file[0:each_file.index(".")].replace("alloneline", "")
                    experiment_type = each_folder.replace("_", "")

                    with open(os.path.join(csv_location, each_folder, each_file), "r") as read_in, \
                            open("/tmp/%s_%s_core" % (experiment_type, hydrogen_flip_state), "w") as core_file, \
                            open("/tmp/%s_%s_full" % (experiment_type, hydrogen_flip_state), "w") as full_file:
                        for line in read_in:
                            backbone_trim_state = line.split(":")[5]
                            if backbone_trim_state == "core":
                                core_file.write(line)
                            elif backbone_trim_state == "full":
                                full_file.write(line)

                    for backbone_trim_state in ['full', 'core']:
                        cur_file = "/tmp/%s_%s_%s" % (experiment_type, hydrogen_flip_state, backbone_trim_state)

                        # Run the stat calculating program
                        logging.info(os.path.join(script_dir, "calculate_statistics"), cur_file, experiment_type,
                                     hydrogen_flip_state, backbone_trim_state)
                        stats_calc = Popen([os.path.join(script_dir, "calculate_statistics"), cur_file, experiment_type,
                                            hydrogen_flip_state, backbone_trim_state], stdout=PIPE, stderr=PIPE)

                        # Copy to the results to the appropriate table
                        cur.copy_from(stats_calc.stderr, 'distributions_working', sep=",", null="-1")
                        cur.copy_from(stats_calc.stdout, 'averages_working', sep=",", null="-1.000000")

                        stats_calc.wait()

            conn.commit()

        cur.execute("DROP TABLE IF EXISTS molprobity.averages;")
        cur.execute("ALTER TABLE molprobity.averages_working RENAME TO averages;")
        cur.execute("DROP TABLE IF EXISTS molprobity.distributions;")
        cur.execute("ALTER TABLE molprobity.distributions_working RENAME TO distributions;")
        cur.execute("ANALYZE molprobity.averages;")
        conn.commit()

        # Load the PDB csv data
        logging.info("Loading PDB information...")
        pdb_url = "http://www.rcsb.org/pdb/rest/customReport.csv?pdbids=*&customReportColumns=structureId," \
                  "structureTitle,experimentalTechnique&format=csv&service=wsfile"
        pdb_csv = StringIO(urlopen(pdb_url).read())
        cur.execute("DROP TABLE IF EXISTS molprobity.pdb_info_working;")
        cur.execute("CREATE TABLE molprobity.pdb_info_working(pdb TEXT, title TEXT, experiment_type TEXT);")
        cur.copy_expert("COPY molprobity.pdb_info_working from STDIN WITH CSV HEADER QUOTE '\"';", pdb_csv)
        # Update which entries are available
        cur.execute("ALTER TABLE molprobity.pdb_info_working ADD COLUMN valid BOOLEAN DEFAULT False;")
        cur.execute("""
UPDATE molprobity.pdb_info_working
  SET valid = True
  WHERE LOWER(pdb_info_working.pdb) IN (SELECT distinct(pdb) FROM averages);""")
        cur.execute("DROP TABLE IF EXISTS molprobity.pdb_info;")
        cur.execute("ALTER TABLE molprobity.pdb_info_working RENAME TO pdb_info;")
        conn.commit()

        logging.info("Generating line chart data...")
        json_dictionary = {}

        for experiment_type in experiment_types:
            json_dictionary[experiment_type] = {}
            for hydrogen_flip_state in hydrogen_flip_states:
                json_dictionary[experiment_type][hydrogen_flip_state] = {}
                for backbone_trim_state in backbone_trim_states:
                    json_dictionary[experiment_type][hydrogen_flip_state][backbone_trim_state] = {}
                    for data_field in data_fields:
                        # Query the DB
                        cur.execute(f"""
    SELECT {data_field}_abs,{data_field}_count FROM molprobity.distributions
    WHERE {data_field}_abs IS NOT NULL
      AND experiment_type = %s
      AND hydrogen_flip_state = %s
      AND backbone_trim_state = %s
    ORDER BY {data_field}_abs;""", [experiment_type, hydrogen_flip_state, backbone_trim_state])
                        results = cur.fetchall()

                        num_res = sum([x[1] for x in results])
                        mod_factor = int(num_res / resolution)
                        if mod_factor == 0:
                            mod_factor = 1

                        # Print the correct number of results
                        processed_list = []
                        mod_counter = 0
                        for x in results:
                            for i in range(0, x[1]):
                                mod_counter += 1
                                if mod_counter % mod_factor == 0:
                                    processed_list.append(round(x[0], 4))

                        json_dictionary[experiment_type][hydrogen_flip_state][backbone_trim_state][
                            data_field] = processed_list

        # Write the json file
        with open(os.path.join(script_dir, "..", "data.js"), "w") as json_file:
            json_file.write("encoded_data=" + json.dumps(json_dictionary))


def molprobity(host=configuration['postgres']['host'],
               database=configuration['postgres']['database'],
               user=configuration['postgres']['reload_user']) -> bool:
    """ This takes a long time. """

    cmd = subprocess.Popen('LC_ALL=C find %s/residue_files/combined/ -name \\*.csv -print0 | xargs -0 cat | '
                           'sort -u -i -S2G --compress-program gzip -' %
                           configuration['molprobity_directory'], shell=True, stderr=subprocess.PIPE,
                           stdout=subprocess.PIPE)

    psql = PostgresConnection(user=user, host=host, database=database)
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
