#!/usr/bin/python3

import csv
import logging
import xml.etree.ElementTree as ET

import requests


class MappingFile:

    def __init__(self, file_name):
        self._file_name = file_name
        self.mapping = {}

    def __enter__(self):
        try:
            with open(self._file_name, 'r') as input_file:
                self.mapping = {x[0]: x[1] for x in csv.reader(input_file)}
        except FileNotFoundError:
            self.mapping = {}
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.save()

    def save(self):
        with open(self._file_name, 'w') as out_file:
            csv_writer = csv.writer(out_file)
            csv_writer.writerows([[x, self.mapping[x]] for x in self.mapping.keys()])


class UniProtMapper(MappingFile):

    def get_uniprot(self, nickname: str):
        """ Returns the official UniProt ID from the nickname.

         Example: P4R3A_HUMAN -> Q6IN85"""

        if nickname:
            logging.info(f'Getting UniProt from nickname {nickname}')
        else:
            return None

        nickname = nickname.upper()
        if "_" not in nickname:
            return nickname

        # In case they specified multiple things
        if " " in nickname:
            for item in nickname.split(" "):
                nick = self.get_uniprot(item)
                if nick:
                    return nick
            return None

        if nickname in self.mapping:
            return self.mapping[nickname]

        mapping_url = f'https://www.uniprot.org/uniprot/?query={nickname}&sort=score&desc=' \
                      '&compress=no&fil=&limit=1&force=no&preview=true&format=tab&columns=id'
        result = requests.get(mapping_url).text.split('\n')[1]
        self.mapping[nickname] = result

        return result


class PDBMapper(MappingFile):

    def get_uniprot(self, pdb_id: str, chain: str):
        """ Returns the official UniProt ID from the PDB ID and chain."""

        if pdb_id and chain:
            logging.info(f'Getting UniProt from PDB {pdb_id}.{chain}')

        if not pdb_id:
            return None

        if chain:
            key = f'{pdb_id}.{chain}'
        else:
            key = pdb_id
        if key in self.mapping:
            return self.mapping[key]

        # Load the PDB ID chains into the mapping
        mapping_url = f'http://www.rcsb.org/pdb/rest/describeMol?structureId={pdb_id}'
        root = ET.fromstring(requests.get(mapping_url).text)
        num_polymers = len(list(root.iter('polymer')))
        for polymer in root.iter('polymer'):
            # Get the UniProt for the polymer
            try:
                uniprot_accession = polymer.findall('macroMolecule/accession')[0].attrib.get('id', None)
            except IndexError:
                uniprot_accession = None

            # Add each chain
            for chain_elem in polymer.findall('chain'):
                pdb_chain = chain_elem.attrib.get('id')
                chain_key = f'{pdb_id}.{pdb_chain}'

                self.mapping[chain_key] = uniprot_accession

            # Add the whole ID
            if num_polymers == 1:
                self.mapping[pdb_id] = uniprot_accession

        # If the chain isn't in the PDB file
        if key not in self.mapping:
            logging.warning("Unknown chain: %s", key)
            self.mapping[key] = None

        return self.mapping.get(key, None)


with UniProtMapper('uniname.csv') as uni_name, PDBMapper('pdb_uniprot.csv') as pdb_map:
    sequences = csv.reader(open('sequences.csv', 'r'))
    headers = next(sequences)
    sequences_out = csv.writer(open('sequences_uniprot.csv', 'w'))

    headers.insert(5, 'Uniprot_ID_from_pdb_id')
    sequences_out.writerow(headers)
    for line in sequences:
        pdb_id = line[3].upper()
        full_chain_id = line[2].upper()
        if full_chain_id:
            chain_id = full_chain_id[0]
        else:
            chain_id = None

        uniprot_id = pdb_map.get_uniprot(pdb_id, chain_id)
        if uniprot_id:
            line.insert(5, uniprot_id)
        else:
            line.insert(5, None)
            if len(full_chain_id) > 1 and pdb_id:
                logging.warning('A multichar sequence didn\'t match: %s.%s', pdb_id, full_chain_id)

        # Make sure the author didn't provide a nickname
        if "_" in line[4]:
            line[4] = uni_name.get_uniprot(line[4])

        sequences_out.writerow(line)


sql = '''
SELECT ent."Entry_ID"                AS "BMRB_ID",
       "ID"                          AS "Entity_ID",
       upper("Polymer_strand_ID")    AS "PDB_chain",
       pdb_id                        AS "PDB_ID",
       dbl."Accession_code"          AS "Uniprot_ID",
       "Polymer_seq_one_letter_code" AS "Sequence",
       "Details"
FROM macromolecules."Entity" AS ent
         LEFT JOIN web.pdb_link AS pdb ON pdb.bmrb_id = ent."Entry_ID"
         LEFT JOIN macromolecules."Entity_db_link" AS dbl
                   ON dbl."Entry_ID" = ent."Entry_ID" AND ent."ID" = dbl."Entity_ID"
WHERE "Polymer_seq_one_letter_code" IS NOT NULL
  AND "Polymer_seq_one_letter_code" != ''
  AND ent."Polymer_type" = 'polypeptide(L)'
  AND ent."Entry_ID"::int > 3000
  AND (dbl."Accession_code" IS NULL
    OR (dbl."Author_supplied" = 'yes' AND
        (lower(dbl."Database_code") = 'unp' OR lower(dbl."Database_code") = 'uniprot')))
ORDER BY ent."Entry_ID"::int, "ID"::int;'''