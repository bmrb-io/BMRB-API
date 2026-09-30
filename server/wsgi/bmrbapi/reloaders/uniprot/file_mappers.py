import csv
import logging
import os
import re

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

this_dir = os.path.dirname(os.path.abspath(__file__))

# Rate limits and brief outages are retried; anything still failing after that
# raises rather than being treated as "no mapping". A lookup that silently
# returns None drops the row from uniprot_mappings, and a run during an outage
# would publish a table missing every mapping it could not look up.
_session = requests.Session()
_session.mount('https://', HTTPAdapter(max_retries=Retry(
    total=5, backoff_factor=2, status_forcelist=(429, 500, 502, 503, 504), allowed_methods=('GET',))))


def _get(url, **kwargs):
    return _session.get(url, timeout=60, **kwargs)


# UniProtKB accession format, from https://www.uniprot.org/help/accession_numbers
_ACCESSION = re.compile(r'[OPQ][0-9][A-Z0-9]{3}[0-9]|[A-NR-Z][0-9]([A-Z][A-Z0-9]{2}[0-9]){1,2}')


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

        # The legacy www.uniprot.org query API was retired in 2022; it now
        # answers with a one-line JSON error, and splitting that on newlines
        # raised an IndexError that killed the whole reloader.
        # active:true because inactive entries keep the name they had: id:B2MG_HUMAN alone also
        #  matches the retired P01884, and which of the two came first varied from call to call.
        response = _get('https://rest.uniprot.org/uniprotkb/search',
                        params={'query': f'id:{nickname} AND active:true', 'fields': 'accession',
                                'format': 'tsv', 'size': 1})
        response.raise_for_status()
        # A header line, then one accession if the entry name matched
        lines = response.text.splitlines()
        result = lines[1].strip() if len(lines) > 1 else None

        # Unreviewed (TrEMBL) entry names are <accession>_<species>, and UniProt has renamed some
        #  species codes since BMRB depositions quoted them (A5VHK8_LACRD is now A5VHK8_LIMRD), so
        #  an old name can stop matching. The accession is still in it; the validator checks it.
        if result is None:
            prefix = nickname.split('_')[0]
            if _ACCESSION.fullmatch(prefix):
                result = prefix

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

        # Load the PDB ID chains into the mapping, from PDBe's SIFTS mappings.
        #  RCSB retired the describeMol REST API this used in 2020; since then
        #  every lookup got a 404 HTML page, failed to parse, and returned None,
        #  so no 'pdb' links were found for anything not already cached.
        response = _get(f'https://www.ebi.ac.uk/pdbe/api/mappings/uniprot/{pdb_id.lower()}')
        if response.status_code == 404:
            # PDBe's answer for an entry with no UniProt mapping (e.g. nucleic acid only)
            unp = {}
        else:
            response.raise_for_status()
            unp = response.json().get(pdb_id.lower(), {}).get('UniProt', {})

        entities = {}
        for uniprot_accession, details in unp.items():
            for chain_map in details.get('mappings', []):
                # chain_id is the author chain ID, as describeMol's was. A chimeric chain maps to
                #  more than one accession; keep the first, as the old code kept the first accession.
                self.mapping.setdefault(f'{pdb_id}.{chain_map["chain_id"]}', uniprot_accession)
                entities.setdefault(chain_map['entity_id'], uniprot_accession)

        # Add the whole ID, when there is only one protein it could mean
        if len(entities) == 1:
            self.mapping[pdb_id] = next(iter(entities.values()))

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

        # This used to read the entry XML and loop over its <accession> elements, keeping each in
        #  turn -- so it ended on the *last* one, a secondary accession: P0CG48 came back as Q9UPK7,
        #  which UniProt has since made an inactive entry of its own. The primary accession is what
        #  a link should carry.
        response = _get(f'https://rest.uniprot.org/uniprotkb/{uniprot_id}.json', params={'fields': 'accession'})
        if response.status_code in (400, 404):
            # 400 is how UniProt answers a string that is not accession-shaped
            result = None
        else:
            response.raise_for_status()
            entry = response.json()
            if entry.get('entryType') == 'Inactive':
                reason = entry.get('inactiveReason', {})
                targets = reason.get('mergeDemergeTo') or []
                # Merged into one entry: follow it. Demerged into several, or deleted: there is no
                #  single right answer, so no mapping.
                if reason.get('inactiveReasonType') == 'MERGED' and len(targets) == 1:
                    result = targets[0]
                else:
                    logging.warning('Inactive UniProt ID (%s) found in BMRB ID %s: %s',
                                    reason.get('inactiveReasonType'), bmrb_id, uniprot_id)
                    result = None
            else:
                result = entry.get('primaryAccession')

        # If the UniProt ID wasn't found
        if result is None and response.status_code in (400, 404):
            logging.warning('Invalid UniProt ID found in BMRB ID %s: %s', bmrb_id, uniprot_id)
        self.mapping[uniprot_id] = result

        return result


