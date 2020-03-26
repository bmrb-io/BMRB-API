import os
import subprocess
import textwrap
import warnings
from decimal import Decimal
from tempfile import NamedTemporaryFile
from typing import List, Dict, Iterable
from urllib.parse import quote

import psycopg2
from flask import jsonify, request, Blueprint, url_for
from psycopg2 import ProgrammingError

# Set up the blueprint
import bmrbapi.views.sql.search as sql_statements
from bmrbapi.exceptions import RequestException, ServerException
from bmrbapi.utils.configuration import configuration
from bmrbapi.utils.connections import PostgresConnection
from bmrbapi.utils.decorators import require_content_type_json
from bmrbapi.utils.querymod import SUBMODULE_DIR, get_db, get_entry_id_tag, select, \
    get_database_from_entry_id, get_valid_entries_from_redis, \
    get_category_and_tag, wrap_it_up, select as querymod_select

search_endpoints = Blueprint('search', __name__)


def get_extra_data_available(bmrb_id):
    """ Returns any additional data associated with the entry. For example:

    Time domain, residual dipolar couplings, pKa values, etc."""

    # Set up the DB cursor
    with PostgresConnection(schema=get_database_from_entry_id(bmrb_id)) as cur:

        query = '''
SELECT "Entry_ID" as entry_id, ed."Type" as type, dic.catgrpviewname as description, "Count"::integer as sets,
       0 as size from "Data_set" as ed
  LEFT JOIN dict.aditcatgrp as dic ON ed."Type" = dic.sfcategory
 WHERE ed."Entry_ID" like %s
UNION
SELECT bmrbid, 'time_domain_data', 'Time domain data', sets, size FROM web.timedomain_data where bmrbid like %s;'''
        cur.execute(query, [bmrb_id, bmrb_id])

        try:
            entry = next(get_valid_entries_from_redis(bmrb_id))[1]
        # This happens when an entry is valid but isn't available in Redis - for example, when we only have
        #  2.0 records for an entry.
        except StopIteration:
            return []

        extra_data = []
        for row in cur.fetchall():
            if row['type'] == 'time_domain_data':
                extra_data.append({'data_type': row['description'], 'data_sets': row['sets'], 'size': row['size'],
                                   'thumbnail_url': url_for('static', filename='fid.svg', _external=True),
                                   'urls': ['ftp://ftp.bmrb.wisc.edu/pub/bmrb/timedomain/bmr%s/' % bmrb_id]})
            elif row['type'] != "assigned_chemical_shifts":
                saveframe_names = [x.name for x in entry.get_saveframes_by_category(row['type'])]
                url = 'http://www.bmrb.wisc.edu/data_library/summary/showGeneralSF.php?accNum=%s&Sf_framecode=%s'

                extra_data.append({'data_type': row['description'], 'data_sets': row['sets'],
                                   'data_sfcategory': row['type'],
                                   'urls': [url % (bmrb_id, quote(x)) for x in saveframe_names]})

    return extra_data


def get_bmrb_ids_from_pdb_id(pdb_id: str) -> List[Dict[str, str]]:
    """ Returns the associated BMRB IDs for a PDB ID. """

    with PostgresConnection() as cur:
        query = '''
        SELECT bmrb_id, array_agg(link_type) from 
    (SELECT bmrb_id, 'Exact' AS link_type, null AS comment
      FROM web.pdb_link
      WHERE pdb_id LIKE UPPER(%s)
    UNION
    SELECT "Entry_ID", 'Author Provided', "Relationship"
      FROM macromolecules."Related_entries"
      WHERE "Database_accession_code" LIKE UPPER(%s) AND "Database_name" = 'PDB'
        AND "Relationship" != 'BMRB Entry Tracking System'
    UNION
    SELECT "Entry_ID", 'Author Provided', "Entry_details"
      FROM macromolecules."Entity_db_link"
      WHERE "Accession_code" LIKE UPPER(%s) AND "Database_code" = 'PDB' AND "Author_supplied" = 'yes'
    UNION
    SELECT "Entry_ID", 'Author Provided', "Entry_details"
      FROM macromolecules."Assembly_db_link"
      WHERE "Accession_code" LIKE UPPER(%s) AND "Database_code" = 'PDB' AND "Author_supplied" = 'yes'
    UNION
    SELECT "Entry_ID", 'BLAST Match', "Entry_details"
      FROM macromolecules."Entity_db_link"
      WHERE "Accession_code" LIKE UPPER(%s) AND "Database_code" = 'PDB' AND "Author_supplied" != 'yes') AS sub
    GROUP BY bmrb_id;'''

        cur.execute(query, [pdb_id, pdb_id, pdb_id, pdb_id, pdb_id])

        result = []
        for x in cur.fetchall():
            result.append({"bmrb_id": x[0], "match_types": x[1]})

        return result


@search_endpoints.route('/search/get_bmrb_data_from_pdb_id/<pdb_id>')
def get_bmrb_data_from_pdb_id(pdb_id):
    """ Returns the associated BMRB data for a PDB ID. """

    result = []
    for item in get_bmrb_ids_from_pdb_id(pdb_id):
        data = get_extra_data_available(item['bmrb_id'])
        if data:
            result.append({'bmrb_id': item['bmrb_id'], 'match_types': item['match_types'],
                           'url': 'http://www.bmrb.wisc.edu/data_library/summary/index.php?bmrbId=%s' % item['bmrb_id'],
                           'data': data})

    return jsonify(result)


@search_endpoints.route('/search/multiple_shift_search')
def multiple_shift_search():
    """ Finds entries that match at least some of the chemical shifts. """

    shift_strings: List[str] = request.args.getlist('shift')
    if not shift_strings:
        shift_strings = request.args.getlist('s')
    else:
        shift_strings.extend(list(request.args.getlist('s')))

    thresholds = {'N': float(request.args.get('nthresh', .2)),
                  'C': float(request.args.get('cthresh', .2)),
                  'H': float(request.args.get('hthresh', .01))}

    if not shift_strings:
        raise RequestException("You must specify at least one shift to search for.")

    sql = '''
SELECT atom_shift."Entry_ID",atom_shift."Assigned_chem_shift_list_ID"::text,
  array_agg(DISTINCT  atom_shift."Val" || ',' ||  atom_shift."Atom_type") as shift_pair,ent.title,ent.link
FROM "Atom_chem_shift" as atom_shift
LEFT JOIN web.instant_cache as ent
  ON ent.id = atom_shift."Entry_ID"
WHERE '''
    terms = []

    shift_floats: List[float] = []
    shift_decimals: List[Decimal] = []
    shift = None
    try:
        for shift in shift_strings:
            shift_floats.append(float(shift))
            shift_decimals.append(Decimal(shift))
    except ValueError:
        raise RequestException("Invalid shift specified. All shifts must be numbers. Invalid shift: '%s'" % shift)

    shift_floats = sorted(shift_floats)
    shift_decimals = sorted(shift_decimals)

    for shift in shift_floats:
        sql += '''
((atom_shift."Val"::float <= %s  AND atom_shift."Val"::float >= %s AND atom_shift."Atom_type" = 'C')
 OR
 (atom_shift."Val"::float <= %s  AND atom_shift."Val"::float >= %s AND atom_shift."Atom_type" = 'N')
 OR
 (atom_shift."Val"::float <= %s  AND atom_shift."Val"::float >= %s AND atom_shift."Atom_type" = 'H')) OR '''
        terms.append(shift + thresholds['C'])
        terms.append(shift - thresholds['C'])
        terms.append(shift + thresholds['N'])
        terms.append(shift - thresholds['N'])
        terms.append(shift + thresholds['H'])
        terms.append(shift - thresholds['H'])

    # End the OR
    sql += '''
1=2
GROUP BY atom_shift."Entry_ID",atom_shift."Assigned_chem_shift_list_ID",ent.title,ent.link
ORDER BY count(DISTINCT atom_shift."Val") DESC;
    '''

    # Do the query
    with PostgresConnection(schema=get_db("metabolomics")) as cur:
        cur.execute(sql, terms)
        result = {"data": []}

        # Send query string if in debug mode
        if configuration['debug']:
            result['debug'] = cur.query

        for entry in cur:
            title = entry[3].replace("\n", "") if entry[3] else None
            # Perfect opportunity for walrus operator once using 3.8
            shifts = [{'Shift': Decimal(y[0]), 'Atom_type': y[1]} for y in [x.split(',') for x in entry[2]]]

            result['data'].append({'Entry_ID': entry[0], 'Assigned_chem_shift_list_ID': entry[1], 'Title': title,
                                   'Link': entry[4], 'Val': shifts})

    def get_closest(collection, number):
        """ Returns the closest number from a list of numbers. """
        return min(collection, key=lambda _: abs(_ - number))

    def get_closest_by_atom(collection: dict,
                            shift_value: Decimal) -> dict:
        """ Returns the closest [shift,atom_name] pair from the options. """

        # Start with impossibly bad peak of the correct atom type, in case no matches for this peak exist
        best_match: dict = {'Shift': Decimal('inf'), 'Atom_type': None}
        for item in collection:
            if abs(item['Shift'] - shift_value) < best_match['Shift']:
                best_match = {'Shift': item['Shift'], 'Atom_type': item['Atom_type']}
        return best_match

    def get_sort_key(res) -> [int, Decimal, str]:
        """ Returns the sort key. """

        key: Decimal = Decimal(0)

        # Add the difference of all the shifts
        for item in res['Val']:
            key += abs(get_closest(shift_decimals, item['Shift']) - item['Shift'])
        res['Combined_offset'] = round(key, 3)

        # Determine how many of the queried shifts were matched
        num_match = 0
        for check_peak in shift_decimals:
            closest = get_closest_by_atom(res['Val'], check_peak)
            if abs(check_peak - closest['Shift']) <= thresholds[closest['Atom_type']]:
                num_match += 1
        res['Shifts_matched'] = num_match

        return -num_match, key, res['Entry_ID']

    result['data'] = sorted(result['data'], key=get_sort_key)

    return jsonify(result)


@search_endpoints.route('/search/chemical_shifts')
def get_chemical_shifts():
    """ Return a list of all chemical shifts that match the selectors"""

    shift_val: Iterable[float] = request.args.getlist('shift')
    threshold: float = float(request.args.get('threshold', .03))
    atom_type: str = request.args.get('atom_type', None)
    atom_id: str = request.args.getlist('atom_id')
    comp_id: str = request.args.getlist('comp_id')
    conditions: bool = request.args.get('conditions', False)
    database: str = get_db("macromolecules")

    sql = '''
SELECT cs."Entry_ID"                          AS "Atom_chem_shift.Entry_ID",
       "Entity_ID"::integer                   AS "Atom_chem_shift.Entity_ID",
       "Comp_index_ID"::integer               AS "Atom_chem_shift.Comp_index_ID",
       "Comp_ID"                              AS "Atom_chem_shift.Comp_ID",
       "Atom_ID"                              AS "Atom_chem_shift.Atom_ID",
       "Atom_type"                            AS "Atom_chem_shift.Atom_type",
       cs."Val"::numeric                      AS "Atom_chem_shift.Val",
       cs."Val_err"::numeric                  AS "Atom_chem_shift.Val_err",
       "Ambiguity_code"                       AS "Atom_chem_shift.Ambiguity_code",
       "Assigned_chem_shift_list_ID"::integer AS "Atom_chem_shift.Assigned_chem_shift_list_ID"
FROM "Atom_chem_shift" AS cs
WHERE
'''

    if conditions:
        sql = '''
SELECT cs."Entry_ID"                          AS "Atom_chem_shift.Entry_ID",
       "Entity_ID"::integer                   AS "Atom_chem_shift.Entity_ID",
       "Comp_index_ID"::integer               AS "Atom_chem_shift.Comp_index_ID",
       "Comp_ID"                              AS "Atom_chem_shift.Comp_ID",
       "Atom_ID"                              AS "Atom_chem_shift.Atom_ID",
       "Atom_type"                            AS "Atom_chem_shift.Atom_type",
       cs."Val"::numeric                      AS "Atom_chem_shift.Val",
       cs."Val_err"::numeric                  AS "Atom_chem_shift.Val_err",
       "Ambiguity_code"                       AS "Atom_chem_shift.Ambiguity_code",
       "Assigned_chem_shift_list_ID"::integer AS "Atom_chem_shift.Assigned_chem_shift_list_ID",
       web.convert_to_numeric(ph."Val")       AS "Sample_conditions.pH",
       web.convert_to_numeric(temp."Val")     AS "Sample_conditions.Temperature_K"
FROM "Atom_chem_shift" AS cs
         LEFT JOIN "Assigned_chem_shift_list" AS csf
                   ON csf."ID" = cs."Assigned_chem_shift_list_ID" AND csf."Entry_ID" = cs."Entry_ID"
         LEFT JOIN "Sample_condition_variable" AS ph
                   ON csf."Sample_condition_list_ID" = ph."Sample_condition_list_ID" AND
                      ph."Entry_ID" = cs."Entry_ID" AND ph."Type" = 'pH'
         LEFT JOIN "Sample_condition_variable" AS temp
                   ON csf."Sample_condition_list_ID" = temp."Sample_condition_list_ID" AND
                      temp."Entry_ID" = cs."Entry_ID" AND
                      temp."Type" = 'temperature' AND temp."Val_units" = 'K'
WHERE
'''

    args = []

    # See if a specific atom type is needed
    if atom_type:
        sql += '''"Atom_type" = %s AND '''
        args.append(atom_type.upper())

    # See if a specific atom is needed
    if atom_id:
        sql += "("
        for atom in atom_id:
            sql += '''"Atom_ID" LIKE %s OR '''
            args.append(atom.replace("*", "%").upper())
        sql += "1 = 2) AND "

    # See if a specific residue is needed
    if comp_id:
        sql += "("
        for comp in comp_id:
            sql += '''"Comp_ID" = %s OR '''
            args.append(comp.upper())
        sql += "1 = 2) AND "

    # See if a peak is specified
    if shift_val:
        sql += "("
        for val in shift_val:
            sql += '''(cs."Val"::float  < %s AND cs."Val"::float > %s) OR '''
            range_low = float(val) - threshold
            range_high = float(val) + threshold
            args.append(range_high)
            args.append(range_low)
        sql += "1 = 2) AND "

    # Make sure the SQL query syntax works out
    sql += '''1=1'''

    result = {}

    # Do the query
    with PostgresConnection(schema=database) as cur:
        cur.execute(sql, args)

        # Send query string if in debug mode
        if configuration['debug']:
            result['debug'] = cur.query

        result['columns'] = [desc[0] for desc in cur.description]
        result['data'] = cur.fetchall()
    return jsonify(result)


@search_endpoints.route('/search/get_all_values_for_tag/<tag_name>')
def get_all_values_for_tag(tag_name):
    """ Returns all entry numbers and corresponding tag values."""

    database = get_db('macromolecules')

    params = get_category_and_tag(tag_name)
    with PostgresConnection(schema=database) as cur:

        # Use Entry_ID normally, but occasionally use ID depending on the context
        id_field = get_entry_id_tag(tag_name, database=database)

        query = '''SELECT "%s", array_agg(%%s) from "%s" GROUP BY "%s";'''
        query = query % (id_field, params[0], id_field)
        try:
            cur.execute(query, [wrap_it_up(params[1])])
        except ProgrammingError as e:
            sp = str(e).split('\n')
            if len(sp) > 3:
                if sp[3].strip().startswith("HINT:  Perhaps you meant to reference the column"):
                    raise RequestException("Tag not found. Did you mean the tag: '%s'?" %
                                           sp[3].split('"')[1])

            raise RequestException("Tag not found.")

        # Turn the results into a dict
        res = {}
        for x in cur.fetchall():
            sub_res = []
            for elem in x[1]:
                if elem and elem != "na":
                    sub_res.append(elem)
            if len(sub_res) > 0:
                res[x[0]] = sub_res

        if configuration['debug']:
            res['query'] = cur.query

    return res


@search_endpoints.route('/search/get_id_by_tag_value/<tag_name>/<path:tag_value>')
def get_id_from_search(tag_name, tag_value):
    """ Returns all BMRB IDs that were found when querying for entries
    which contain the supplied value for the supplied tag. """

    database = get_db('macromolecules', valid_list=['metabolomics', 'macromolecules', 'chemcomps'])

    sp = tag_name.split(".")
    if sp[0].startswith("_"):
        sp[0] = sp[0][1:]
    if len(sp) < 2:
        raise RequestException("You must provide a full tag name with saveframe included. For example: "
                               "Entry.Experimental_method_subtype")

    id_field = get_entry_id_tag(tag_name, database)
    result = select([id_field], sp[0], where_dict={sp[1]: tag_value}, modifiers=['lower'], database=database)
    return jsonify(result[list(result.keys())[0]])


@search_endpoints.route('/search/get_bmrb_ids_from_pdb_id/<pdb_id>')
def get_bmrb_ids_from_pdb_id_route(pdb_id):
    """ Returns the associated BMRB IDs for a PDB ID. """

    return jsonify(get_bmrb_ids_from_pdb_id(pdb_id))


@search_endpoints.route('/search/get_pdb_ids_from_bmrb_id/<bmrb_id>')
def get_pdb_ids_from_bmrb_id(bmrb_id):
    """ Returns the associated PDB IDs for a BMRB ID. """

    with PostgresConnection() as cur:
        query = '''
    SELECT pdb_id, 'Exact' AS link_type, null AS comment
      FROM web.pdb_link
      WHERE bmrb_id LIKE %s
    UNION
    SELECT "Database_accession_code", 'Author Provided', "Relationship"
      FROM macromolecules."Related_entries"
      WHERE "Entry_ID" LIKE %s AND "Database_name" = 'PDB'
        AND "Relationship" != 'BMRB Entry Tracking System'
    UNION
    SELECT "Accession_code", 'Author Provided', "Entry_details"
      FROM macromolecules."Entity_db_link"
      WHERE "Entry_ID" LIKE %s AND "Database_code" = 'PDB' AND "Author_supplied" = 'yes'
    UNION
    SELECT "Accession_code", 'Author Provided', "Entry_details"
      FROM macromolecules."Assembly_db_link"
      WHERE "Entry_ID" LIKE %s AND "Database_code" = 'PDB' AND "Author_supplied" = 'yes'
    UNION
    SELECT "Accession_code", 'BLAST Match', "Entry_details"
      FROM macromolecules."Entity_db_link"
      WHERE "Entry_ID" LIKE %s AND "Database_code" = 'PDB' AND "Author_supplied" != 'yes';'''

        cur.execute(query, [bmrb_id, bmrb_id, bmrb_id, bmrb_id, bmrb_id])
        return jsonify([{"pdb_id": x[0], "match_type": x[1], "comment": x[2]} for x in cur.fetchall()])


@search_endpoints.route('/search/fasta/<sequence>')
def fasta_search(sequence):
    """Performs a FASTA search on the specified query in the BMRB database."""

    fasta_binary = os.path.join(SUBMODULE_DIR, "fasta36", "bin", "fasta36")
    a_type = request.args.get('type', 'polymer')
    e_val = request.args.get('e_val')

    # Map the type to the exact name
    a_type = {'polymer': 'polypeptide(L)', 'rna': 'polyribonucleotide', 'dna': 'polydeoxyribonucleotide'}[a_type]

    if not os.path.isfile(fasta_binary):
        raise ServerException("Unable to perform FASTA search. Server improperly installed.")

    with PostgresConnection(schema="macromolecules") as cur:
        cur.execute('''
SELECT ROW_NUMBER() OVER (ORDER BY 1) AS id, entity."Entry_ID",entity."ID",
  regexp_replace(entity."Polymer_seq_one_letter_code", E'[\\n\\r]+', '', 'g' ),
  replace(regexp_replace(entry."Title", E'[\\n\\r]+', ' ', 'g' ), '  ', ' ')
FROM "Entity" as entity
  LEFT JOIN "Entry" as entry
  ON entity."Entry_ID" = entry."ID"
  WHERE entity."Polymer_seq_one_letter_code" IS NOT NULL AND "Polymer_type" = %s''', [a_type])

        sequences = cur.fetchall()

    wrapper = textwrap.TextWrapper(width=80, expand_tabs=False,
                                   replace_whitespace=False,
                                   drop_whitespace=False, break_on_hyphens=False)
    seq_strings = [">%s\n%s\n" % (x[0], "\n".join(wrapper.wrap(x[3]))) for x in sequences]

    # Use temporary files to store the FASTA search string and FASTA DB
    with NamedTemporaryFile(dir="/dev/shm") as fasta_file, \
            NamedTemporaryFile(dir="/dev/shm") as sequence_file:
        fasta_file.file.write((">query\n%s" % sequence.upper()).encode())
        fasta_file.flush()

        sequence_file.file.write(("".join(seq_strings)).encode())
        sequence_file.flush()

        # Set up the FASTA arguments
        fasta_arguments = [fasta_binary, "-m", "8"]
        if e_val:
            fasta_arguments.extend(["-E", e_val])
        fasta_arguments.extend([fasta_file.name, sequence_file.name])

        # Run FASTA
        res = subprocess.check_output(fasta_arguments, stderr=subprocess.STDOUT).decode()

    # Combine the results
    results = []
    for line in res.split("\n"):
        cols = line.split()
        if len(cols) == 12:
            matching_row = sequences[int(cols[1]) - 1]
            results.append({'entry_id': matching_row[1], 'entity_id': matching_row[2],
                            'entry_title': matching_row[4], 'percent_id': Decimal(cols[2]),
                            'alignment_length': int(cols[3]), 'mismatches': int(cols[4]),
                            'gap_openings': int(cols[5]), 'q.start': int(cols[6]),
                            'q.end': int(cols[7]), 's.start': int(cols[8]), 's.end': int(cols[9]),
                            'e-value': Decimal(cols[10]), 'bit_score': Decimal(cols[11])})

    return jsonify(results)


@search_endpoints.route('/instant')
def reroute_instant_internal():
    warnings.warn('Please use /search/instant.', DeprecationWarning)
    return instant()


@search_endpoints.route('/search/instant')
def instant():
    """ Do the instant search. """

    term = request.args.get('term')
    database = get_db('combined')

    if database == "metabolomics":
        instant_query_one = sql_statements.metabolomics_instant_query_one
        instant_query_two = sql_statements.metabolomics_instant_query_two

    elif database == "macromolecules":
        instant_query_one = sql_statements.macromolecules_instant_query_one
        instant_query_two = sql_statements.macromolecules_instant_query_two
    else:
        instant_query_one = sql_statements.combined_instant_query_one
        instant_query_two = sql_statements.combined_instant_query_two

    with PostgresConnection() as cur:
        try:
            cur.execute(instant_query_one, [term, term, term])
        except psycopg2.ProgrammingError:
            if configuration['debug']:
                raise
            return [{"label": "Instant search temporarily offline.", "value": "error",
                     "link": "/software/query/"}]

        # First query
        result = []
        ids = {}
        for item in cur.fetchall():
            res = {"citations": item['citations'],
                   "authors": item['authors'],
                   "link": item['link'],
                   "value": item['id'],
                   "sub_date": str(item['sub_date']),
                   "label": "%s" % (item['title'])}

            if database == "metabolomics":
                res['formula'] = item['formula']
                res['smiles'] = item['smiles']
                res['inchi'] = item['inchi']
                res['monoisotopic_mass'] = item['monoisotopic_mass']
                res['average_mass'] = item['average_mass']
                res['molecular_weight'] = item['molecular_weight']

            result.append(res)
            ids[item['id']] = 1

        debug = {}
        if configuration['debug']:
            debug['query1'] = cur.query

        # Second query
        try:
            cur.execute(instant_query_two, [term, term, term, term])
        except psycopg2.ProgrammingError:
            if configuration['debug']:
                raise
            return [{"label": "Instant search temporarily offline.", "value": "error",
                     "link": "/software/query/"}]

        for item in cur.fetchall():
            if item['id'] not in ids:
                res = {"citations": item['citations'],
                       "authors": item['authors'],
                       "link": item['link'],
                       "value": item['id'],
                       "sub_date": str(item['sub_date']),
                       "label": "%s" % (item['title']),
                       "extra": {"term": item['term'],
                                 "termname": item['termname']},
                       "sml": "%s" % item['sml']}
                if database == "metabolomics":
                    res['formula'] = item['formula']
                    res['smiles'] = item['smiles']
                    res['inchi'] = item['inchi']
                    res['monoisotopic_mass'] = item['monoisotopic_mass']
                    res['average_mass'] = item['average_mass']
                    res['molecular_weight'] = item['molecular_weight']

                result.append(res)
        if configuration['debug']:
            debug['query2'] = cur.query
            result.append({"debug": debug})

    return jsonify(result)


@search_endpoints.route('/select', methods=['POST'])
@require_content_type_json
def select():
    """ Performs an advanced select query. """

    params: dict = request.json

    # Get the database name
    database = params.get("database", "macromolecules")

    if database == "combined":
        raise RequestException('Merged database not yet available.')
    if database not in ["chemcomps", "macromolecules", "metabolomics", "dict"]:
        raise RequestException("Invalid database specified.")

    # Okay, now we need to go through each query and get the results
    if not isinstance(params['query'], list):
        params['query'] = [params['query']]

    result_list = []

    # Build the amalgamation of queries
    for each_query in params['query']:

        # For one query:
        each_query['select'] = each_query.get("select", ["Entry_ID"])
        if not isinstance(each_query['select'], list):
            each_query['select'] = [each_query['select']]
        # We need the ID to join if they are doing multiple queries
        if len(params['query']) > 1:
            each_query['select'].append("Entry_ID")
        if "from" not in each_query:
            raise RequestException('You must specify which table to query with the "from" parameter.')
        if "dict" not in each_query:
            each_query['dict'] = True

        # Get the query modifiers
        each_query['modifiers'] = each_query.get("modifiers", [])
        if not isinstance(each_query['modifiers'], list):
            each_query['modifiers'] = [each_query['modifiers']]

        each_query['where'] = each_query.get("where", {})

        if len(params['query']) > 1:
            # If there are multiple queries then add their results to the list
            cur_res = querymod_select(each_query['select'], each_query['from'],
                                      where_dict=each_query['where'], database=database,
                                      modifiers=each_query['modifiers'], as_dict=False)
            result_list.append(cur_res)
        else:
            # If there is only one query just return it
            return querymod_select(each_query['select'], each_query['from'],
                                   where_dict=each_query['where'], database=database,
                                   modifiers=each_query['modifiers'],
                                   as_dict=each_query['dict'])

    return result_list
