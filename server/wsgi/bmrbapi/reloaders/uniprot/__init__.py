import csv
import logging
import os

from psycopg2.extras import execute_values

from bmrbapi.reloaders.uniprot import sql_statements as sql_statements
from bmrbapi.reloaders.uniprot.file_mappers import UniProtMapper, PDBMapper, UniProtValidator
from bmrbapi.utils.configuration import configuration
from bmrbapi.utils.connections import PostgresConnection


def uniprot(host=configuration['postgres']['host'],
            database=configuration['postgres']['database'],
            user=configuration['postgres']['reload_user']):
    psql_conn = PostgresConnection(user=user, host=host, database=database)
    this_dir = os.path.dirname(os.path.abspath(__file__))
    with UniProtMapper('uniname.csv') as uni_name, \
            PDBMapper('pdb_uniprot.csv') as pdb_map, \
            UniProtValidator('uniprot_validate.csv') as uniprot_validator, \
            open(os.path.join(this_dir, 'sequences_uniprot.csv'), 'w') as uniprot_seq_file, \
            psql_conn as cur:

        cur.execute(sql_statements.author_and_pdb_links)
        sequences = cur.fetchall()
        for line in sequences:
            for pos, item in enumerate(line):
                if item is None:
                    line[pos] = ''

        sequences_out = csv.writer(uniprot_seq_file)
        sequences_out.writerow(
            ['bmrb_id', 'entity_id', 'pdb_chain', 'pdb_id', 'link_type', 'uniprot_id', 'protein_sequence', 'details'])

        for line in sequences:
            pdb_id = line[3].upper()
            full_chain_id = line[2].upper()
            if full_chain_id:
                chain_id = full_chain_id[0]
            else:
                chain_id = None

            # Only search for a UniProt ID if we don't already have an author one
            if not line[5]:
                uniprot_id = pdb_map.get_uniprot(pdb_id, chain_id, bmrb_id=line[0])
                if uniprot_id:
                    line[4] = 'PDB cross-referencing'
                    line[5] = uniprot_id
                else:
                    if len(full_chain_id) > 1 and pdb_id:
                        logging.info('A multichar sequence didn\'t match: %s.%s', pdb_id, full_chain_id)

            # Make sure the author didn't provide a nickname
            if "." in line[5]:
                line[5] = line[5].replace('.', '-')
            if "_" in line[5]:
                line[5] = uni_name.get_uniprot(line[5])

            # Validate the uniprot
            line[5] = uniprot_validator.validate_uniprot(line[5], line[0])

            sequences_out.writerow(line)
        uniprot_seq_file.close()

        # Put it in postgresql
        def row_gen():
            with open(os.path.join(this_dir, 'sequences_uniprot.csv'), 'r') as seq_file_read:
                csv_reader = csv.reader(seq_file_read)
                next(csv_reader)
                for each_line in csv_reader:
                    yield each_line

        cur.execute(sql_statements.create_mappings_table)
        execute_values(cur, sql_statements.bulk_insert, row_gen(), page_size=100)
        cur.execute(sql_statements.insert_clean_ready)
        psql_conn.commit()
