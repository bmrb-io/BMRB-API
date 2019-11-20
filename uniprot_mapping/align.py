#!/usr/bin/python3

import csv
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
            print(f'Getting UniProt from nickname {nickname}')
        else:
            return None

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

        if pdb_id and chain:
            print(f'Getting UniProt from PDB {pdb_id}.{chain}')
        else:
            return None

        pdb_id = pdb_id.upper()
        chain = chain.upper()

        key = f'{pdb_id}.{chain}'
        if key in self.mapping:
            return self.mapping[key]

        mapping_url = f'http://www.rcsb.org/pdb/rest/describeMol?structureId={pdb_id}'
        root = ET.fromstring(requests.get(mapping_url).text)

        for polymer in root.iter('polymer'):
            pdb_chain = polymer.findall('chain')[0].attrib.get('id')
            chain_key = f'{pdb_id}.{pdb_chain}'
            try:
                uniprot_accession = polymer.findall('macroMolecule/accession')[0].attrib.get('id', None)
                if pdb_chain:
                    self.mapping[chain_key] = uniprot_accession
            except IndexError:
                self.mapping[chain_key] = None

        return self.mapping.get(key, None)


with UniProtMapper('uniname.csv') as uni_name, PDBMapper('pdb_uniprot.csv') as pdb_map:
    sequences = csv.reader(open('sequences.csv', 'r'))
    headers = next(sequences)
    sequences_out = csv.writer(open('sequences_uniprot.csv', 'w'))

    headers.insert(5, 'Uniprot_ID_from_pdb_id')
    sequences_out.writerow(headers)
    for line in sequences:
        pdb_id = line[3].upper()
        for chain in line[2].upper().split(','):
            to_insert = list(line)

            uniprot_id = pdb_map.get_uniprot(pdb_id, chain)
            if uniprot_id:
                to_insert.insert(5, uniprot_id)
            else:
                to_insert.insert(5, None)
            to_insert[2] = chain

            # Make sure the author didn't provide a nickname
            if "_" in to_insert[4]:
                to_insert[4] = uni_name.get_uniprot(to_insert[4])

            sequences_out.writerow(to_insert)
