import csv
import logging
import os
import xml
from xml.etree import ElementTree

import requests

this_dir = os.path.dirname(os.path.abspath(__file__))


class MappingFile:

    def __init__(self, file_name):
        self._file_name = os.path.join(this_dir, file_name)
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

    def get_uniprot(self, pdb_id: str, chain: str, bmrb_id=None):
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
        try:
            root = ElementTree.fromstring(requests.get(mapping_url).text)
        except xml.etree.ElementTree.ParseError:
            return None

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
            logging.warning("Unknown chain in BMRB ID %s: %s", bmrb_id, key)
            self.mapping[key] = None

        return self.mapping.get(key, None)


class UniProtValidator(MappingFile):

    def validate_uniprot(self, uniprot_id: str, bmrb_id: str = None):
        """ Returns the official UniProt ID from a UniProt ID. """

        if uniprot_id:
            logging.info(f'Validating UniProt {uniprot_id}.')
        else:
            return None
        if uniprot_id in self.mapping:
            return self.mapping[uniprot_id]

        # Get the UniProt XML
        mapping_url = f'http://www.uniprot.org/uniprot/{uniprot_id}.xml'

        try:
            root = ElementTree.fromstring(requests.get(mapping_url).text)
            # Add all the mappings found
            for entry in root.iter('{http://uniprot.org/uniprot}entry'):
                for accession in entry.iter('{http://uniprot.org/uniprot}accession'):
                    self.mapping[uniprot_id] = accession.text
        except xml.etree.ElementTree.ParseError:
            pass
            # Use https://www.uniprot.org/uniparc/?query=Q7U294&format=tab&limit=10&columns=id,kb&sort=score
            #  with taxonomy ID to map these

        # If the UniProt ID wasn't found
        if uniprot_id not in self.mapping:
            logging.warning('Invalid UniProt ID found in BMRB ID %s: %s', bmrb_id, uniprot_id)
            self.mapping[uniprot_id] = None

        return self.mapping[uniprot_id]


