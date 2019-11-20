#!/usr/bin/python3

import csv

import requests

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

        sequences_out.writerow(to_insert)


def get_uniprot_from_nickname(nickname: str):
    """ Returns the official uniprot ID from the nickname.

     Example: P4R3A_HUMAN -> Q6IN85"""

    nickname = nickname.upper()
    if "_" not in nickname:
        return nickname

    try:
        uni_map = {x[0]: x[1] for x in csv.reader(open('uniname.csv', 'r'))}
    except FileNotFoundError:
        uni_map = {}
    if nickname in uni_map:
        return uni_map[nickname]

    mapping_url = f'https://www.uniprot.org/uniprot/?query={nickname}&sort=score&desc=&compress=no&fil=&limit=1&force=no&preview=true&format=tab&columns=id'
    result = requests.get(mapping_url).text.split('\n')[1]

    uni_map[nickname] = result
    writer = csv.writer(open('uniname.csv', 'w'))
    writer.writerows([[x, uni_map[x]] for x in uni_map.keys()])

