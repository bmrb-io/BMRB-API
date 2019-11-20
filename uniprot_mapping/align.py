#!/usr/bin/python3

import csv
import xml.etree.ElementTree as ET
import requests

a = """
sequences = csv.reader(open('sequences.csv', 'r'))
headers = next(sequences)
sequences_out = csv.writer(open('sequences_uniprot.csv', 'w'))

# Generated from https://www.uniprot.org/uploadlists/
mapping = open('pdb_uniprot.tab', 'r')
backup_map = {}
for line in mapping:
    columns = line.split()
    for pdb in columns[0].split(','):
        if pdb in backup_map:
            backup_map[pdb].append(columns[1])
        else:
            backup_map[pdb] = [columns[1]]

# Generated from:
uniprot_map = {}
mapping = open('pdbsws_chain.txt', 'r')
for line in mapping:
    try:
        pdb, chain, uniprot = line.split()
    except ValueError:
        pdb, chain = line.split()
        uniprot = None
    if pdb.upper() in uniprot_map:
        uniprot_map[pdb.upper()][chain.upper()] = uniprot
    else:
        uniprot_map[pdb.upper()] = {chain.upper(): uniprot}

# Or to get real serious (and slow)
# http://www.rcsb.org/pdb/rest/describeMol?structureId=2AST

headers.insert(5, 'Uniprot_ID_from_pdb_id')
sequences_out.writerow(headers)
for line in sequences:
    chain_ids = line[2].upper().split(',')
    for chain in chain_ids:
        uniprot_id = uniprot_map.get(line[3], {}).get(line[2], None)
        if uniprot_id == "?":
            uniprot_id = None

        to_insert = list(line)
        if uniprot_id:
            to_insert.insert(5, uniprot_id)
        else:
            if line[3] in backup_map:
                to_insert.insert(5, ",".join(backup_map[line[3]]))
            else:
                to_insert.insert(5, None)
        to_insert[2] = chain

        sequences_out.writerow(to_insert)"""


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

        with open(self._file_name, 'w') as out_file:
            csv_writer = csv.writer(out_file)
            csv_writer.writerows([[x, self.mapping[x]] for x in self.mapping.keys()])


class UniProtMapper(MappingFile):

    def get_uniprot(self, nickname: str):
        """ Returns the official UniProt ID from the nickname.

         Example: P4R3A_HUMAN -> Q6IN85"""

        nickname = nickname.upper()
        if "_" not in nickname:
            return nickname

        if nickname in self.mapping:
            return self.mapping[nickname]

        mapping_url = f'https://www.uniprot.org/uniprot/?query={nickname}&sort=score&desc=' \
                      '&compress=no&fil=&limit=1&force=no&preview=true&format=tab&columns=id'
        result = requests.get(mapping_url).text.split('\n')[1]
        self.mapping[nickname] = result

        return result


class PDBMapper(MappingFile):

    def get_uniprot(self, pdb_id: str, chain: str):
        """ Returns the official uniprot ID from the PDB ID and chain."""

        pdb_id = pdb_id.upper()
        chain = chain.upper()

        key = f'{pdb_id}.{chain}'
        if key in self.mapping:
            return self.mapping[key]

        mapping_url = f'http://www.rcsb.org/pdb/rest/describeMol?structureId={pdb_id}'
        root = ET.fromstring(requests.get(mapping_url).text)

        for polymer in root.iter('polymer'):
            pdb_chain = polymer.findall('chain')[0].attrib.get('id')
            uniprot_accession = polymer.findall('macroMolecule/accession')[0].attrib.get('id', None)
            if pdb_chain and uniprot_accession:
                self.mapping[f'{pdb_id}.{pdb_chain}'] = uniprot_accession

        return self.mapping.get(key, None)



with UniProtMapper('uniname.csv') as uni_name:
    print(uni_name.get_uniprot('P4R3A_HUMAN'))

with PDBMapper('pdb_uniprot.csv') as pdb_map:
    print(pdb_map.get_uniprot('2AST', 'A'))
