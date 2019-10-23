# Requirements.txt
import os
import subprocess
import textwrap
from decimal import Decimal
from tempfile import NamedTemporaryFile
from typing import List

from flask import jsonify, request, Blueprint

# Local modules
from bmrbapi.utils.querymod import RequestError, ServerError, SUBMODULE_DIR, get_postgres_connection, set_database, \
    get_extra_data_available, get_db, get_all_values_for_tag, get_entry_id_tag, select, get_pdb_ids_from_bmrb_id, \
    get_bmrb_ids_from_pdb_id, chemical_shift_search_1d, configuration

# Set up the blueprint
user_endpoints = Blueprint('search', __name__)


@user_endpoints.route('/search')
@user_endpoints.route('/search/')
def print_search_options():
    """ Returns a list of the search methods."""

    result = ""
    for method in ["chemical_shifts", "fasta", "get_all_values_for_tag", "get_bmrb_data_from_pdb_id",
                   "get_id_by_tag_value", "get_bmrb_ids_from_pdb_id",
                   "get_pdb_ids_from_bmrb_id", "multiple_shift_search"]:
        result += '<a href="%s">%s</a><br>' % (method, method)

    return result


@user_endpoints.route('/search/get_bmrb_data_from_pdb_id/')
@user_endpoints.route('/search/get_bmrb_data_from_pdb_id/<pdb_id>')
def get_bmrb_data_from_pdb_id(pdb_id=None):
    """ Returns the associated BMRB data for a PDB ID. """

    if not pdb_id:
        raise RequestError("You must specify a PDB ID.")

    result = []
    for item in get_bmrb_ids_from_pdb_id(pdb_id):
        data = get_extra_data_available(item['bmrb_id'])
        if data:
            result.append({'bmrb_id': item['bmrb_id'], 'match_types': item['match_types'],
                           'url': 'http://www.bmrb.wisc.edu/data_library/summary/index.php?bmrbId=%s' % item['bmrb_id'],
                           'data': data})

    return jsonify(result)


@user_endpoints.route('/search/multiple_shift_search')
def multiple_shift_search():
    """ Finds entries that match at least some of the chemical shifts. """

    shift_strings: List[str] = request.args.getlist('shift')
    if not shift_strings:
        shift_strings = request.args.getlist('s')
    else:
        shift_strings.extend(list(request.args.getlist('s')))

    try:
        thresholds = {'N': float(request.args.get('nthresh', .2)),
                      'C': float(request.args.get('cthresh', .2)),
                      'H': float(request.args.get('hthresh', .01))}
    except ValueError:
        raise RequestError("Invalid threshold specified. Please specify the threshold as a float which will be"
                           " interpreted as a PPM value.")

    if not shift_strings:
        raise RequestError("You must specify at least one shift to search for.")

    cur = get_postgres_connection()[1]
    set_database(cur, get_db("metabolomics"))

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
        raise RequestError("Invalid shift specified. All shifts must be numbers. Invalid shift: '%s'" % shift)

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


@user_endpoints.route('/search/chemical_shifts')
def get_chemical_shifts():
    """ Return a list of all chemical shifts that match the selectors"""

    cs1d = chemical_shift_search_1d
    return jsonify(cs1d(shift_val=request.args.getlist('shift'),
                        threshold=request.args.get('threshold', .03),
                        atom_type=request.args.get('atom_type', None),
                        atom_id=request.args.getlist('atom_id'),
                        comp_id=request.args.getlist('comp_id'),
                        conditions=request.args.get('conditions', False),
                        database=get_db("macromolecules")))


@user_endpoints.route('/search/get_all_values_for_tag/')
@user_endpoints.route('/search/get_all_values_for_tag/<tag_name>')
def get_all_values_for_tag(tag_name=None):
    """ Returns all entry numbers and corresponding tag values."""

    result = get_all_values_for_tag(tag_name, get_db('macromolecules'))
    return jsonify(result)


@user_endpoints.route('/search/get_id_by_tag_value/')
@user_endpoints.route('/search/get_id_by_tag_value/<tag_name>/')
@user_endpoints.route('/search/get_id_by_tag_value/<tag_name>/<path:tag_value>')
def get_id_from_search(tag_name=None, tag_value=None):
    """ Returns all BMRB IDs that were found when querying for entries
    which contain the supplied value for the supplied tag. """

    database = get_db('macromolecules', valid_list=['metabolomics', 'macromolecules', 'chemcomps'])

    if not tag_name:
        raise RequestError("You must specify the tag name.")
    if not tag_value:
        raise RequestError("You must specify the tag value.")

    sp = tag_name.split(".")
    if sp[0].startswith("_"):
        sp[0] = sp[0][1:]
    if len(sp) < 2:
        raise RequestError("You must provide a full tag name with saveframe included. For example: "
                           "Entry.Experimental_method_subtype")

    id_field = get_entry_id_tag(tag_name, database)
    result = select([id_field], sp[0], where_dict={sp[1]: tag_value}, modifiers=['lower'], database=database)
    return jsonify(result[list(result.keys())[0]])


@user_endpoints.route('/search/get_bmrb_ids_from_pdb_id/')
@user_endpoints.route('/search/get_bmrb_ids_from_pdb_id/<pdb_id>')
def get_bmrb_ids_from_pdb_id(pdb_id=None):
    """ Returns the associated BMRB IDs for a PDB ID. """

    if not pdb_id:
        raise RequestError("You must specify a PDB ID.")

    result = get_bmrb_ids_from_pdb_id(pdb_id)
    return jsonify(result)


@user_endpoints.route('/search/get_pdb_ids_from_bmrb_id/')
@user_endpoints.route('/search/get_pdb_ids_from_bmrb_id/<pdb_id>')
def get_pdb_ids_from_bmrb_id(pdb_id=None):
    """ Returns the associated BMRB IDs for a PDB ID. """

    if not pdb_id:
        raise RequestError("You must specify a BMRB ID.")

    result = get_pdb_ids_from_bmrb_id(pdb_id)
    return jsonify(result)


@user_endpoints.route('/search/fasta/')
@user_endpoints.route('/search/fasta/<query>')
def fasta_search(query=None):
    """Performs a FASTA search on the specified query in the BMRB database."""

    if not query:
        raise RequestError("You must specify a sequence.")

    fasta_binary = os.path.join(SUBMODULE_DIR, "fasta36", "bin", "fasta36")
    a_type = request.args.get('type', 'polymer')
    e_val = request.args.get('e_val')

    # Make sure the type is valid
    if a_type not in ["polymer", "rna", "dna"]:
        raise RequestError("Invalid search type: %s" % a_type)
    # Map the type to the exact name
    a_type = {'polymer': 'polypeptide(L)', 'rna': 'polyribonucleotide', 'dna': 'polydeoxyribonucleotide'}[a_type]

    if not os.path.isfile(fasta_binary):
        raise ServerError("Unable to perform FASTA search. Server improperly installed.")

    cur = get_postgres_connection()[1]
    set_database(cur, "macromolecules")
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
        fasta_file.file.write((">query\n%s" % query.upper()).encode())
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
