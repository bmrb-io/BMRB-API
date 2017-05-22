#!/usr/bin/env python

""" This module provides methods to service the different query types that are
provided through the REST and JSON-RPC interfaces. This is where the real work
is done; jsonapi.wsgi and restapi.wsgi mainly just call the methods here and
return the results."""

# Make sure print functions work in python2 and python3
from __future__ import print_function

# Module level defines
__all__ = ['create_chemcomp_from_db', 'create_saveframe_from_db', 'get_tags',
           'get_loops', 'get_saveframes', 'get_entries',
           'get_redis_connection', 'get_postgres_connection', 'get_status',
           'list_entries', 'select', 'configuration', 'get_enumerations',
           'store_uploaded_entry']

_METHODS = ['list_entries', 'chemical_shifts', 'entry',
            'status', 'select', 'software/', 'validate/', 'instant',
            'enumerations', 'search/get_id_by_tag_value/']

import os
import json
import zlib
import logging
import subprocess
from hashlib import md5
from time import time as unixtime
from tempfile import NamedTemporaryFile

import psycopg2
from psycopg2.extensions import AsIs
from psycopg2.extras import execute_values, DictCursor
from psycopg2 import ProgrammingError
import redis
from redis.sentinel import Sentinel

# Local imports
import bmrb

class ServerError(Exception):
    """ Something is wrong with the server. """
    status_code = 500

    def __init__(self, message, status_code=None, payload=None):
        Exception.__init__(self)
        self.message = message
        if status_code is not None:
            self.status_code = status_code
        self.payload = payload

    def to_dict(self):
        rv = dict(self.payload or ())
        rv['error'] = self.message
        return rv

class RequestError(Exception):
    """ Something is wrong with the request. """
    status_code = 400

    def __init__(self, message, status_code=None, payload=None):
        Exception.__init__(self)
        self.message = message
        if status_code is not None:
            self.status_code = status_code
        self.payload = payload

    def to_dict(self):
        rv = dict(self.payload or ())
        rv['error'] = self.message
        return rv


# Load the configuration file
config_loc = os.path.join(os.path.dirname(os.path.realpath(__file__)),
                          "..", "..", "..", "..", "api_config.json")
configuration = json.loads(open(config_loc, "r").read())

# Load local configuration overrides
config_loc = os.path.join(os.path.dirname(os.path.realpath(__file__)),
                          "..", "..", "..", "api_config.json")
if os.path.isfile(config_loc):
    config_overrides = json.loads(open(config_loc, "r").read())
    for config_param in config_overrides:
        configuration[config_param] = config_overrides[config_param]

# Determine submodules folder
_SUBMODULE_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.realpath(__file__))),
                              "submodules")

# Set up logging
logging.basicConfig()

def check_local_ip(ip):
    """ Checks if the given IP is a local user."""

    for local_address in configuration['local-ips']:
        if local_address.startswith(ip):
            return True

    return False

def insert_db(db, query):
    """ Make sure they specified a valid DB and then insert it into the
    query. """

    if db not in ["metabolomics", "macromolecules", "combined"]:
        raise RequestError("Invalid database: %s." % db)

    return query.replace("DB_SCHEMA_MAGIC_STRING", db)

def locate_entry(entry_id, r_conn=None):
    """ Determines what the Redis key is for an entry given the database
    provided."""

    if entry_id.startswith("bm"):
        return "metabolomics:entry:%s" % entry_id
    elif entry_id.startswith("chemcomp"):
        return "chemcomps:entry:%s" % entry_id
    elif len(entry_id) == 32:
        entry_loc = "uploaded:entry:%s" % entry_id

        # Update the expiration time if the entry is used
        if r_conn is None:
            r_conn = get_redis_connection()
        if r_conn.exists(entry_loc):
            r_conn.expire(entry_loc, configuration['redis']['upload_timeout'])

        return entry_loc
    else:
        return "macromolecules:entry:%s" % entry_id

def check_valid(entry_id, r_conn=None):
    """ Returns whether an entry_is is valid. """

    # Update the expiration time if the entry is used
    if r_conn is None:
        r_conn = get_redis_connection()

    return r_conn.exists(locate_entry(entry_id, r_conn=r_conn))

def get_database_from_entry_id(entry_id):
    """ Returns the appropriate database to inspect based on ID."""

    if entry_id.startswith("bm"):
        return "metabolomics"
    else:
        return "macromolecules"

def get_postgres_connection(user=configuration['postgres']['user'],
                            host=configuration['postgres']['host'],
                            database=configuration['postgres']['database'],
                            dictionary_cursor=False):
    """ Returns a connection to postgres and a cursor."""

    # Errors connecting will be handled upstream
    if dictionary_cursor:
        conn = psycopg2.connect(user=user, host=host, database=database, cursor_factory=DictCursor)
    else:
        conn = psycopg2.connect(user=user, host=host, database=database)
    cur = conn.cursor()

    return conn, cur

def get_redis_connection(db=None):
    """ Figures out where the master redis instance is (and other paramaters
    needed to connect like which database to use), and opens a connection
    to it. It passes back that connection object."""

    # Connect to redis
    try:
        # Figure out where we should connect
        sentinel = Sentinel(configuration['redis']['sentinels'],
                            socket_timeout=0.5)
        redis_host, redis_port = sentinel.discover_master(configuration['redis']['master_name'])

        # If they didn't specify a DB then use the configuration default
        if db is None:
            db = configuration['redis']['db']

        # Get the redis instance
        r = redis.StrictRedis(host=redis_host,
                              port=redis_port,
                              password=configuration['redis']['password'],
                              db=db)

    # Raise an exception if we cannot connect to the database server
    except (redis.exceptions.ConnectionError,
            redis.sentinel.MasterNotFoundError):
        raise ServerError('Could not connect to database server.')

    return r

def get_all_entries_from_redis(format_="object", database="macromolecules"):
    """ Returns a generator that returns all the entries from a given
    database from Redis."""

    # Get the connection to redis
    r = get_redis_connection()
    all_ids = list(r.lrange("%s:entry_list" % database, 0, -1))

    return get_valid_entries_from_redis(all_ids, format_=format_,
                                        max_results=float("Inf"))

def get_valid_entries_from_redis(search_ids, format_="object", max_results=500):
    """ Given a list of entries, yield the subset that exist in the database
    as the appropriate type as determined by the "format_" variable.

    Valid entry formats:
    nmrstar: Return the entry as NMR-STAR text
    json: Return the entry in serialized JSON format
    dict: Return the entry JSON data as a python dict
    object: Return the PyNMR-STAR object for the entry
    zlib: Return the entry straight from the DB as zlib compressed JSON
    """

    # Wrap the IDs in a list if necessary
    if not isinstance(search_ids, list):
        search_ids = [search_ids]

    # Make sure all the entry ids are strings
    search_ids = [str(x) for x in search_ids]

    # Make sure there are not too many entries
    if len(search_ids) > max_results:
        raise RequestError('Too many IDs queried. Please query %s '
                           'or fewer entries at a time. You attempted to '
                           'query %d IDs.' % (max_results, len(search_ids)))

    # Get the connection to redis
    r = get_redis_connection()

    # Go through the IDs
    for entry_id in search_ids:

        entry = r.get(locate_entry(entry_id, r_conn=r))

        # See if it is in redis
        if entry:
            # Return the compressed entry
            if format_ == "zlib":
                yield (entry_id, entry)

            else:
                # Uncompress the zlib into serialized JSON
                entry = zlib.decompress(entry)
                if format_ == "json":
                    yield (entry_id, entry)
                else:
                    # Parse the JSON into python dict
                    entry = json.loads(entry)
                    if format_ == "dict":
                        yield (entry_id, entry)
                    else:
                        # Parse the dict into object
                        entry = bmrb.Entry.from_json(entry)
                        if format_ == "object":
                            yield (entry_id, entry)
                        else:
                            # Return NMR-STAR
                            if format_ == "nmrstar" or format_ == "rawnmrstar":
                                yield (entry_id, str(entry))

                            # Unknown format
                            else:
                                raise RequestError("Invalid format: %s." % format_)

def store_uploaded_entry(**kwargs):
    """ Store an uploaded NMR-STAR file in the database."""

    uploaded_data = kwargs.get("data", None)

    if not uploaded_data:
        raise RequestError("No data uploaded. Please post the "
                           "NMR-STAR file as the request body.")

    try:
        parsed_star = bmrb.Entry.from_string(uploaded_data)
    except ValueError as e:
        raise RequestError("Invalid uploaded NMR-STAR file."
                           " Exception: %s" % str(e))

    key = md5(uploaded_data).digest().encode("hex")

    r = get_redis_connection()
    r.setex("uploaded:entry:%s" % key, configuration['redis']['upload_timeout'],
            zlib.compress(parsed_star.get_json()))

    return {"entry_id": key,
            "expiration": unixtime() + configuration['redis']['upload_timeout']}

def panav_parser(panav_text):
    """ Parses the PANAV data into something jsonify-able."""

    lines = panav_text.split("\n")

    # Initialize the result dictionary
    result = {}
    result['offsets'] = {}
    result['deviants'] = []
    result['suspicious'] = []
    result['text'] = panav_text

    # Variables to keep track of output line numbers
    deviant_line = 5
    suspicious_line = 6


    # There is an error
    if len(lines) < 3:
        raise ServerError("PANAV failed to produce expected output."
                          " Output: %s" % panav_text)

    # Check for unusual output
    if "No reference" in lines[0]:
        # Handle the special case when no offsets
        result['offsets'] = {'CO': 0, 'CA': 0, 'CB': 0, 'N': 0}
        deviant_line = 1
        suspicious_line = 2
    # Normal output
    else:
        result['offsets']['CO'] = float(lines[1].split(" ")[-1].replace("ppm",""))
        result['offsets']['CA'] = float(lines[2].split(" ")[-1].replace("ppm",""))
        result['offsets']['CB'] = float(lines[3].split(" ")[-1].replace("ppm",""))
        result['offsets']['N'] = float(lines[4].split(" ")[-1].replace("ppm",""))

    # Figure out how many deviant and suspicious shifts were detected
    num_deviants = int(lines[deviant_line].rstrip().split(" ")[-1])
    num_suspicious = int(lines[suspicious_line + num_deviants].rstrip().split(" ")[-1])
    suspicious_line += num_deviants + 1
    deviant_line += 1

    # Get the deviants
    for deviant in lines[deviant_line:deviant_line+num_deviants]:
        resnum, res, atom, shift = deviant.strip().split(" ")
        result['deviants'].append({"residue_number": resnum, "residue_name": res,
                                   "atom": atom, "chemical_shift_value": shift})

    # Get the suspicious shifts
    for suspicious in lines[suspicious_line:suspicious_line+num_suspicious]:
        resnum, res, atom, shift = suspicious.strip().split(" ")
        result['suspicious'].append({"residue_number": resnum, "residue_name": res,
                                   "atom": atom, "chemical_shift_value": shift})

    # Return the result dictionary
    return result


def get_chemical_shift_validation(**kwargs):
    """ Returns a validation report for the given entry. """

    entries = get_valid_entries_from_redis(kwargs['ids'])

    result = {}

    for entry in entries:

        # AVS
        # There is at least one chem shift saveframe for this entry
        result[entry[0]] = {}
        result[entry[0]]["avs"] = {}
        # Put the chemical shift loop in a file

        with NamedTemporaryFile(dir="/dev/shm") as star_file:
            star_file.file.write(str(entry[1]))
            star_file.flush()

            avs_location = os.path.join(_SUBMODULE_DIR, "avs/validate_assignments_31.pl")
            res = subprocess.check_output([avs_location, entry[0], "-nitrogen", "-fmean",
                                           "-aromatic", "-std", "-anomalous", "-suspicious",
                                           "-star_output", star_file.name],
                                           stderr=subprocess.STDOUT)

            error_loop = bmrb.Entry.from_string(res).get_loops_by_category("_AVS_analysis_r")[0].filter(["Assembly_ID", "Entity_assembly_ID", "Entity_ID", "Comp_index_ID", "Comp_ID", "Comp_overall_assignment_score", "Comp_typing_score", "Comp_SRO_score", "Comp_1H_shifts_analysis_status", "Comp_13C_shifts_analysis_status", "Comp_15N_shifts_analysis_status"])
            error_loop.category = "AVS_analysis"

            # Modify the chemical shift loops with the new data
            shift_lists = entry[1].get_loops_by_category("atom_chem_shift")
            for loop in shift_lists:
                loop.add_column(["AVS_analysis_status", "PANAV_analysis_status"])
                for row in loop.data:
                    row.extend(["Consistent", "Consistent"])

            result[entry[0]]["avs"] = error_loop.get_json(serialize=False)

        # PANAV
        # For each chemical shift loop
        for pos, cs_loop in enumerate(entry[1].get_loops_by_category("atom_chem_shift")):

            # There is at least one chem shift saveframe for this entry
            result[entry[0]]["panav"] = {}
            # Put the chemical shift loop in a file
            with NamedTemporaryFile(dir="/dev/shm") as chem_shifts:
                chem_shifts.file.write(str(cs_loop))
                chem_shifts.flush()

                panav_location = os.path.join(_SUBMODULE_DIR, "panav/panav.jar")
                try:
                    res = subprocess.check_output(["java", "-cp", panav_location,
                                                   "CLI", "-f", "star", "-i", chem_shifts.name],
                                                   stderr=subprocess.STDOUT)
                    # There is a -j option that produces a somewhat usable JSON...
                    result[entry[0]]["panav"][pos] = panav_parser(res)
                except subprocess.CalledProcessError:
                    result[entry[0]]["panav"][pos] = {"error": "PANAV failed on this entry."}

    # Return the result dictionary
    return result

def list_entries(**kwargs):
    """ Returns all valid entry IDs by default. If a database is specified than
    only entries from that database are returned. """

    db = kwargs.get("database", "combined")
    entry_list = get_redis_connection().lrange("%s:entry_list" % db, 0, -1)

    return entry_list

def get_chemical_shifts(**kwargs):
    """ Returns all of the chemical shifts matching the given atom type (if
    specified) and database (if specified)."""


    # Create the search dicationary
    wd = {}
    database = "macromolecules"

    # See if they specified a specific atom type
    if kwargs.get('atom_type', None):
        wd['Atom_ID'] = kwargs['atom_type'].replace("*", "%").upper()

    # See if they specified a database
    if kwargs.get('database', None):
        database = kwargs['database']

    chem_shift_fields = ["Entry_ID", "Entity_ID", "Comp_index_ID", "Comp_ID",
                         "Atom_ID", "Atom_type", "Val", "Val_err",
                         "Ambiguity_code", "Assigned_chem_shift_list_ID"]

    # See if the result is already in Redis
    r = get_redis_connection()
    redis_cache_name = "cache:%s:assigned_chemical_shifts:%s" % (database, wd.get('Atom_ID', 'all'))
    if r.exists(redis_cache_name):
        return json.loads(zlib.decompress(r.get(redis_cache_name)))

    # Perform the query
    query_result = select(chem_shift_fields, "Atom_chem_shift",
                          as_hash=False, where_dict=wd, database=database)
    r.set(redis_cache_name, zlib.compress(json.dumps(query_result)))

    return query_result

def get_tags(**kwargs):
    """ Returns results for the queried tags."""

    # Get the valid IDs and redis connection
    search_tags = process_STAR_query(kwargs)
    result = {}

    # Go through the IDs
    for entry in get_valid_entries_from_redis(kwargs['ids']):
        result[entry[0]] = entry[1].get_tags(search_tags)

    return result

def get_status(**kwargs):
    """ Return some statistics about the server."""

    r = get_redis_connection()
    stats = {}
    for key in ['metabolomics', 'macromolecules', 'chemcomps', 'combined']:
        stats[key] = r.hgetall("%s:meta" % key)
        for skey in stats[key]:
            stats[key][skey] = float(stats[key][skey])

    pg = get_postgres_connection()[1]
    for key in ['metabolomics', 'macromolecules']:
        sql = '''SELECT reltuples FROM pg_class
                 WHERE oid = '%s."Atom_chem_shift"'::regclass;''' % key
        pg.execute(sql)
        stats[key]['num_chemical_shifts'] = pg.fetchone()[0]

    # Add the available methods
    stats['methods'] = _METHODS
    stats['version'] = subprocess.check_output(["git",
                                                "describe",
                                                "--abbrev=0"]).strip()

    return stats

def get_loops(**kwargs):
    """ Returns the matching loops."""

    # Get the valid IDs and redis connection
    loop_categories = process_STAR_query(kwargs)
    result = {}

    # Go through the IDs
    for entry in get_valid_entries_from_redis(kwargs['ids']):
        result[entry[0]] = {}
        for loop_category in loop_categories:
            matches = entry[1].get_loops_by_category(loop_category)

            if kwargs.get('format', "json") == "nmrstar":
                matching_loops = [str(x) for x in matches]
            else:
                matching_loops = [x.get_json(serialize=False) for x in matches]
            result[entry[0]][loop_category] = matching_loops

    return result

def get_enumerations(tag, term=None, cur=None):
    """ Returns a list of enumerations for a given tag from the DB. """

    if cur is None:
        cur = get_postgres_connection()[1]

    if not tag.startswith("_"):
        tag = "_" + tag

    # Get the list of which tags should be used to order data
    cur.execute('''select itemenumclosedflg,enumeratedflg,dictionaryseq from dict.adit_item_tbl where originaltag=%s''', [tag])
    query_res = cur.fetchall()
    if len(query_res) == 0:
        raise RequestError("Invalid tag specified.")

    cur.execute('''select val from dict.enumerations where seq=%s order by val''', [query_res[0][2]])
    values = cur.fetchall()

    # Generate the result dictionary
    result = {}
    result['values'] = [x[0] for x in values]
    if query_res[0][0] == "Y":
        result['type'] = "enumerations"
    elif query_res[0][1] == "Y":
        result['type'] = "common"
    else:
        result['type'] = None

    # Be able to search through enumerations based on the term argument
    if term != None:
        new_result = []
        for val in result['values']:
            if val.startswith(term):
                new_result.append({"value":val, "label":val})
        return new_result

    return result

def chemical_shift_search_1d(shift_val=None, threshold=.03, atom_type=None, atom_id=None, comp_id=None, database="macromolecules"):
    """ Searches for a given chemical shift. """

    cur = get_postgres_connection()[1]

    try:
        threshold = float(threshold)
    except ValueError:
        raise RequestError("Invalid threshold.")

    sql = insert_db(database, '''
SELECT "Entry_ID","Entity_ID","Comp_index_ID","Comp_ID","Atom_ID","Atom_type","Val","Val_err","Ambiguity_code","Assigned_chem_shift_list_ID"
FROM DB_SCHEMA_MAGIC_STRING."Atom_chem_shift"
WHERE ''')
    args = []

    # See if a specific atom type is needed
    if atom_type:
        sql += '''"Atom_chem_shift"."Atom_type"=%s AND '''
        args.append(atom_type.replace("*", "%").upper())

    # See if a specific atom is needed
    if atom_id:
        sql += '''"Atom_chem_shift"."Atom_ID"=%s AND '''
        args.append(atom_id.replace("*", "%").upper())

    # See if a specific residue is needed
    if comp_id:
        sql += '''"Atom_chem_shift"."Comp_ID"=%s AND '''
        args.append(comp_id.replace("*", "%").upper())

    # See if a peak is specified
    if shift_val:
        sql += '''"Atom_chem_shift"."Val"::float  < %s AND "Atom_chem_shift"."Val"::float  > %s AND '''
        range_low = str(float(shift_val) - threshold)
        range_high = str(float(shift_val) + threshold)
        args.append(range_high)
        args.append(range_low)

    # Make sure the SQL query syntax works out
    sql += "1=1"

    # Do the query
    cur.execute(sql, args)

    result = {}

    # Send query string if in debug mode
    if configuration['debug']:
        result['debug'] = cur.query

    result['columns'] = ["Atom_chem_shift." + desc[0] for desc in cur.description]
    result['data'] = cur.fetchall()
    return result

def get_entry_software(entry_id):
    """ Returns the software used for a given entry. """

    database = get_database_from_entry_id(entry_id)

    cur = get_postgres_connection()[1]

    cur.execute(insert_db(database, '''
SELECT "Software"."Name", "Software"."Version", task."Task" as "Task", vendor."Name" as "Vendor Name"
FROM DB_SCHEMA_MAGIC_STRING."Software"
   LEFT JOIN DB_SCHEMA_MAGIC_STRING."Vendor" as vendor ON "Software"."Entry_ID"=vendor."Entry_ID" AND "Software"."ID"=vendor."Software_ID"
   LEFT JOIN DB_SCHEMA_MAGIC_STRING."Task" as task ON "Software"."Entry_ID"=task."Entry_ID" AND "Software"."ID"=task."Software_ID"
WHERE "Software"."Entry_ID"=%s;'''), [entry_id])

    column_names = [desc[0] for desc in cur.description]
    return {"columns": column_names, "data": cur.fetchall()}

def get_software_entries(software_name, database="macromolecules"):
    """ Returns the entries assosciated with a given piece of software. """

    cur = get_postgres_connection()[1]

    # Get the list of which tags should be used to order data
    cur.execute(insert_db(database, '''
SELECT "Software"."Entry_ID", "Software"."Name", "Software"."Version", vendor."Name" as "Vendor Name", vendor."Electronic_address" as "e-mail", task."Task" as "Task"
FROM DB_SCHEMA_MAGIC_STRING."Software"
   LEFT JOIN DB_SCHEMA_MAGIC_STRING."Vendor" as vendor ON "Software"."Entry_ID"=vendor."Entry_ID" AND "Software"."ID"=vendor."Software_ID"
   LEFT JOIN DB_SCHEMA_MAGIC_STRING."Task" as task ON "Software"."Entry_ID"=task."Entry_ID" AND "Software"."ID"=task."Software_ID"
WHERE lower("Software"."Name") like lower(%s);'''), ["%" + software_name + "%"])

    column_names = [desc[0] for desc in cur.description]
    return {"columns": column_names, "data": cur.fetchall()}

def get_software_summary(database="macromolecules"):
    """ Returns all software packages from the DB. """

    cur = get_postgres_connection()[1]

    # Get the list of which tags should be used to order data
    cur.execute(insert_db(database, '''
SELECT "Software"."Name", "Software"."Version", task."Task" as "Task", vendor."Name" as "Vendor Name"
FROM DB_SCHEMA_MAGIC_STRING."Software"
   LEFT JOIN DB_SCHEMA_MAGIC_STRING."Vendor" as vendor ON "Software"."Entry_ID"=vendor."Entry_ID" AND "Software"."ID"=vendor."Software_ID"
   LEFT JOIN DB_SCHEMA_MAGIC_STRING."Task" as task ON "Software"."Entry_ID"=task."Entry_ID" AND "Software"."ID"=task."Software_ID";'''))

    column_names = [desc[0] for desc in cur.description]
    return {"columns": column_names, "data": cur.fetchall()}

def do_sql_mods(conn=None, cur=None, sql_file=None):
    """ Make sure functions we need are saved in the DB. """

    # Re-use existing connection
    if not (conn and cur):
        conn, cur = get_postgres_connection(user=configuration['postgres']['reload_user'])

    if sql_file is None:
        sql_file = os.path.join(os.path.dirname(os.path.realpath(__file__)), "sql", "initialize.sql")
    else:
        sql_file = os.path.join(os.path.dirname(os.path.realpath(__file__)), "sql", sql_file)

    cur.execute(open(sql_file, "r").read())
    conn.commit()

def create_csrosetta_table(csrosetta_sqlite_file):
    """Creates the CS-Rosetta links table."""

    import sqlite3

    c = sqlite3.connect(csrosetta_sqlite_file).cursor()
    entries = c.execute('SELECT key, bmrbid, rosetta_version, csrosetta_version, rmsd_lowest FROM entries;').fetchall()

    pconn, pcur = get_postgres_connection()
    pcur.execute('''
DROP TABLE IF EXISTS web.bmrb_csrosetta_entries;
CREATE TABLE web.bmrb_csrosetta_entries (
 key varchar(13) PRIMARY KEY,
 bmrbid integer,
 rosetta_version
 varchar(5),
 csrosetta_version varchar(5),
 rmsd_lowest float);''')

    execute_values(pcur, '''
INSERT INTO web.bmrb_csrosetta_entries(key, bmrbid, rosetta_version, csrosetta_version, rmsd_lowest)
VALUES %s;''',
              entries)

    pconn.commit()

def build_fulltext_search():
    """ Allows querying the full text of an entry. """

    conn, cur = get_postgres_connection()

    # Metabolomics
    for entry in get_all_entries_from_redis(database="metabolomics"):
        print("Inserting %s" % entry[0]);
        ent_text = get_bmrb_as_text(entry[1])
        cur.execute('''
UPDATE web.instant_cache
SET
 full_tsv=to_tsvector(%s),
 full_text=%s
WHERE id=%s;''',
                    [ent_text, ent_text, entry[0]])
    conn.commit()

    # Macromolecules
    for entry in get_all_entries_from_redis(database="macromolecules"):
        print("Inserting %s" % entry[0]);
        ent_text = get_bmrb_as_text(entry[1])
        cur.execute('''
UPDATE web.instant_cache
SET
 full_tsv=to_tsvector(%s),
 full_text=%s
WHERE id=%s;''',
              [ent_text, ent_text, entry[0]])

    conn.commit()

def get_bmrb_as_text(entry):
    """ Prints the unique set of data in a BMRB entry. """

    res_strings = set()

    for saveframe in entry:
        res_strings.update([x[1].replace("\n", "") for x in saveframe.tags])
        for loop in saveframe:
            for row in loop:
                res_strings.update(row)

    return " ".join(res_strings)

def get_instant_search(term, database):
    """ Does an instant search and returns results. """

    cur = get_postgres_connection(dictionary_cursor=True)[1]

    instant_query_one = '''
SELECT id,title,citations,authors,link,sub_date FROM web.instant_cache
WHERE tsv @@ plainto_tsquery(%s)
ORDER BY id=%s DESC, is_metab ASC, sub_date DESC, ts_rank_cd(tsv, plainto_tsquery(%s)) DESC;'''

    if database == "metabolomics":
        instant_query_one = '''
SELECT id,title,citations,authors,link,sub_date FROM web.instant_cache
WHERE tsv @@ plainto_tsquery(%s) AND is_metab = 'True'
ORDER BY id=%s DESC, is_metab ASC, sub_date DESC, ts_rank_cd(tsv, plainto_tsquery(%s)) DESC;'''
    if database == "macromolecules":
        instant_query_one = '''
SELECT id,title,citations,authors,link,sub_date FROM web.instant_cache
WHERE tsv @@ plainto_tsquery(%s) AND is_metab = 'False'
ORDER BY id=%s DESC, is_metab ASC, sub_date DESC, ts_rank_cd(tsv, plainto_tsquery(%s)) DESC;'''

    instant_query_two = '''
SELECT set_limit(.5);
SELECT DISTINCT on (id) term,termname,'1'::int as sml,tt.id,title,citations,authors,link,sub_date,is_metab FROM web.instant_cache
    LEFT JOIN web.instant_extra_search_terms as tt
    ON instant_cache.id=tt.id
    WHERE tt.identical_term @@ plainto_tsquery(%s)
UNION
SELECT * from (
SELECT DISTINCT on (id) term,termname,similarity(tt.term, %s) as sml,tt.id,title,citations,authors,link,sub_date,is_metab FROM web.instant_cache
    LEFT JOIN web.instant_extra_search_terms as tt
    ON instant_cache.id=tt.id
    WHERE tt.term %% %s AND tt.identical_term IS NULL
    ORDER BY id, similarity(tt.term, %s) DESC) as y'''

    if database == "metabolomics":
        instant_query_two += " WHERE is_metab = 'True'"
    if database == "macromolecules":
        instant_query_two += " WHERE is_metab = 'False'"

    instant_query_two += \
''' ORDER BY sml DESC LIMIT 75;'''

    try:
        cur.execute(instant_query_one, [term, term, term])
    except ProgrammingError:
        return [{"label":"Instant search temporarily offline.", "value":"error",
                 "link":"/software/query/"}]

    # First query
    result = []
    ids = {}
    for item in cur.fetchall():
        result.append({"citations": item['citations'],
                       "authors": item['authors'],
                       "link": item['link'],
                       "value": item['id'],
                       "sub_date": str(item['sub_date']),
                       "label": "%s" % (item['title'])})
        ids[item['id']] = 1


    # Second query
    try:
        cur.execute(instant_query_two, [term, term, term, term])
    except ProgrammingError:
        return [{"label":"Instant search temporarily offline.", "value":"error",
                 "link":"/software/query/"}]

    for item in cur.fetchall():
        if item['id'] not in ids:
            result.append({"citations": item['citations'],
                           "authors": item['authors'],
                           "link": item['link'],
                           "value": item['id'],
                           "sub_date": str(item['sub_date']),
                           "label": "%s" % (item['title']),
                           "extra": {"term": item['term'],
                                     "termname": item['termname']},
                           "sml": "%s" % item['sml']})

    return result

def get_saveframes(**kwargs):
    """ Returns the matching saveframes."""

    # Get the valid IDs and redis connection
    saveframe_categories = process_STAR_query(kwargs)
    result = {}

    # Go through the IDs
    for entry in get_valid_entries_from_redis(kwargs['ids']):
        result[entry[0]] = {}
        for saveframe_category in saveframe_categories:
            matches = entry[1].get_saveframes_by_category(saveframe_category)
            if kwargs.get('format', "json") == "nmrstar":
                matching_frames = [str(x) for x in matches]
            else:
                matching_frames = [x.get_json(serialize=False) for x in matches]
            result[entry[0]][saveframe_category] = matching_frames
    return result

def get_entries(**kwargs):
    """ Returns the full entries."""

    # Check their parameters before proceeding
    process_STAR_query(kwargs)
    result = {}

    # Go through the IDs
    format_ = kwargs.get('format', "json")

    for entry in get_valid_entries_from_redis(kwargs['ids'], format_=format_):
        result[entry[0]] = entry[1]

    return result

def wrap_it_up(item):
    """ Quote items in a way that postgres accepts and that doesn't allow
    SQL injection."""
    return AsIs('"' + item + '"')

def select(fetch_list, table, where_dict=None, database="macromolecules",
           modifiers=None, as_hash=True, cur=None):
    """ Performs a SELECT query constructed from the supplied arguments."""

    # Turn None parameters into the proper empty type
    if where_dict is None:
        where_dict = {}
    if modifiers is None:
        modifiers = []

    # Make sure they aren't tring to inject (paramterized queries are safe while
    # this is not, but there is no way to parameterize a table name...)
    if '"' in table:
        raise RequestError("Invalid 'from' parameter.")

    # Errors connecting will be handled upstream
    if cur is None:
        cur = get_postgres_connection()[1]

    # Prepare the query
    if len(fetch_list) == 1 and fetch_list[0] == "*":
        parameters = []
    else:
        parameters = [wrap_it_up(x) for x in fetch_list]
    query = "SELECT "
    if "count" in modifiers:
        # Build the 'select * from *' part of the query
        query += "count(" + "),count(".join(["%s"]*len(fetch_list))
        query += ') from %s."%s"' % (database, table)
    else:
        if len(fetch_list) == 1 and fetch_list[0] == "*":
            query += '* from %s."%s"' % (database, table)
        else:
            # Build the 'select * from *' part of the query
            query += ",".join(["%s"]*len(fetch_list))
            query += ' from %s."%s"' % (database, table)

    if len(where_dict) > 0:
        query += " WHERE"
        need_and = False

        for key in where_dict:
            if need_and:
                query += " AND"
            if "lower" in modifiers:
                query += " LOWER(%s) LIKE LOWER(%s)"
            else:
                query += " %s LIKE %s"
            parameters.extend([wrap_it_up(key), where_dict[key]])
            need_and = True

# TODO: build ordering in based on dictionary
#    if "count" not in modifiers:
#        query += ' ORDER BY "Entry_ID"'
#        # Order the parameters as ints if they are normal BMRB IDS
#        if database == "macromolecules":
#            query += "::int "

    query += ';'

    # Do the query
    try:
        cur.execute(query, parameters)
        rows = cur.fetchall()
    except psycopg2.ProgrammingError:
        raise RequestError("Invalid 'from' parameter.")

    # Get the column names from the DB
    colnames = [desc[0] for desc in cur.description]

    if not as_hash:
        return {'data':rows, 'columns': [table + "." + x for x in colnames]}

    # Turn the results into a dictionary
    result = {}

    if "count" in modifiers:
        for pos, search_field in enumerate(fetch_list):
            result[table + "." + search_field] = rows[0][pos]
    else:
        for search_field in colnames:
            result[table + "." + search_field] = []
            s_index = colnames.index(search_field)
            for row in rows:
                result[table + "." + search_field].append(row[s_index])

    if configuration['debug']:
        result['debug'] = cur.query

    return result


def process_STAR_query(params):
    """ A helper method that parses the keys out of the query and validates
    the 'ids' parameter."""

    # Make sure they have IDS
    if "ids" not in params:
        raise RequestError('You must specify one or more entry IDs '
                           'with the "ids" parameter.')

    # Set the keys to the empty list if not specified
    if 'keys' not in params:
        params['keys'] = []

    # Wrap the key in a list if necessary
    if not isinstance(params['keys'], list):
        params['keys'] = [params['keys']]

    return params['keys']

def process_select(**params):
    """ Checks the parameters submitted before calling the get_fields_by_fields
    method with them."""

    # Get the database name
    database = params.get("database", "macromolecules")

    if database == "combined":
        raise RequestError('Merged database not yet available.')
    if database not in ["chemcomps", "macromolecules", "metabolomics", "dict"]:
        raise RequestError("Invalid database specified.")

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
            raise RequestError('You must specify which table to '
                               'query with the "from" parameter.')
        if "hash" not in each_query:
            each_query['hash'] = True

        # Get the query modifiers
        each_query['modifiers'] = each_query.get("modifiers", [])
        if not isinstance(each_query['modifiers'], list):
            each_query['modifiers'] = [each_query['modifiers']]

        each_query['where'] = each_query.get("where", {})

        if len(params['query']) > 1:
            # If there are multiple queries then add their results to the list
            cur_res = select(each_query['select'], each_query['from'],
                             where_dict=each_query['where'], database=database,
                             modifiers=each_query['modifiers'], as_hash=False)
            result_list.append(cur_res)
        else:
            # If there is only one query just return it
            return select(each_query['select'], each_query['from'],
                          where_dict=each_query['where'], database=database,
                          modifiers=each_query['modifiers'],
                          as_hash=each_query['hash'])

    return result_list

    # Synchronized list generation - in progress
    common_ids = []
    for pos, result in enumerate(result_list):
        id_pos = params['query'][pos]['select'].index('Entry_ID')
        common_ids.append([x[id_pos] for x in result])

    # Determine the IDs that are in all results
    common_ids = list(set.intersection(*map(set, common_ids)))

    new_response = {}
    for each_id in common_ids:
        for pos, each_query in enumerate(params['query']):
            for field in each_query['select']:
                if each_query['from'] + "." + field not in new_response:
                    new_response[each_query['from'] + "." + field] = []

    return new_response

def create_chemcomp_from_db(chemcomp, cur=None):
    """ Create a chem comp entry from the database."""

    # Rebuild the chemcomp and generate the cc_id. This way we can work
    # with the three letter string or the full chemcomp. Also make sure
    # to capitalize it.
    if len(chemcomp) == 3:
        cc_id = chemcomp.upper()
    else:
        cc_id = chemcomp[9:].upper()
    chemcomp = "chemcomp_" + cc_id

    # Connect to DB
    if cur is None:
        cur = get_postgres_connection()[1]

    # Create entry
    ent = bmrb.Entry.from_scratch(chemcomp)
    chemcomp_frame = create_saveframe_from_db("chemcomps", "chem_comp",
                                              cc_id, "ID", cur)
    entity_frame = create_saveframe_from_db("chemcomps", "entity",
                                            cc_id,
                                            "Nonpolymer_comp_ID", cur)
    # This is specifically omitted... long story
    try:
        del entity_frame['_Entity_atom_list']
    except KeyError:
        pass

    ent.add_saveframe(entity_frame)
    ent.add_saveframe(chemcomp_frame)

    return ent

def get_printable_tags(category, cur=None):
    """ Returns a list of the tags that should be printed for the given
    category and a list of tags that are pointers."""

    # A cursor should always be provided, but just in case
    if cur is None:
        cur = get_postgres_connection()[1]

    # Figure out the loop tags
    cur.execute('''SELECT tagfield,internalflag,printflag,dictionaryseq,sfpointerflag
                FROM dict.val_item_tbl
                WHERE tagcategory=%(loop_name)s ORDER BY dictionaryseq''',
                {"loop_name": category})

    tags_to_use = []
    pointer_tags = []

    # Figure out which tags to print
    for row in cur:
        # See if the tag is a pointer
        if row[4] == "Y":
            pointer_tags.append(row[0])

        # Make sure it isn't internal and it should be printed
        if row[1] != "Y":
            # Make sure it should be printed
            if row[2] == "Y" or row[2] == "O":
                tags_to_use.append(row[0])
            else:
                if configuration['debug']:
                    print("Skipping no print tag: %s" % row[0])
        else:
            if configuration['debug']:
                print("Skipping private tag: %s" % row[0])

    return tags_to_use, pointer_tags

def create_saveframe_from_db(database, category, entry_id, id_search_field,
                             cur=None):
    """ Builds a saveframe from the database. You specify the database:
    (metabolomics, macromolecules, chemcomps, combined), the category of the
    saveframe, the identifier of the saveframe, and the name of the column that
    we should search for the identifier (within the saveframe's table).

    You can optionally pass a cursor to reuse an existing postgresql
    connection."""

    # Connect to the database unless passed a handle
    # Why? If building a whole entry we don't want to have to
    # reconnect a bunch of times. This allows the calling method to
    # provide a connection and cursor.
    if cur is None:
        cur = get_postgres_connection()[1]

    # Look up information about the tags to use later
    #cur.execute('''SELECT val_item_tbl.originaltag,val_item_tbl.internalflag,
    #printflag,val_item_tbl.dictionaryseq,rowindexflg FROM dict.val_item_tbl,
    #dict.adit_item_tbl WHERE val_item_tbl.originaltag=
    #adit_item_tbl.originaltag''')

    # Get the list of which tags should be used to order data
    cur.execute('''SELECT originaltag,rowindexflg from dict.adit_item_tbl''')
    tag_order = {x[0]:x[1] for x in cur.fetchall()}

    # Set the search path
    cur.execute('''SET search_path=%(path)s, pg_catalog;''', {'path':database})

    # Check if we are allowed to print it
    cur.execute('''SELECT internalflag,printflag FROM dict.cat_grp
                WHERE sfcategory=%(sf_cat)s ORDER BY groupid''',
                {'sf_cat': category})
    internalflag, printflag = cur.fetchone()

    # Sorry, we won't print internal saveframes
    if internalflag == "Y":
        logging.warning("Something tried to format an internal saveframe: "
                        "%s.%s", database, category)
        return None
    # Nor frames that don't get printed
    if printflag == "N":
        logging.warning("Something tried to format an no-print saveframe: "
                        "%s.%s", database, category)
        return None

    # Get table name from category name
    cur.execute("""SELECT DISTINCT tagcategory FROM dict.val_item_tbl
                WHERE originalcategory=%(category)s AND loopflag<>'Y'""",
                {"category":category})
    table_name = cur.fetchone()[0]

    if configuration['debug']:
        print("Will look in table: %s" % table_name)

    # Get the sf_id for later
    cur.execute('''SELECT "Sf_ID","Sf_framecode" FROM %(table_name)s
                WHERE %(search_field)s=%(id)s ORDER BY "Sf_ID"''',
                {"id":entry_id, 'table_name': wrap_it_up(table_name),
                 "search_field": wrap_it_up(id_search_field)})

    # There is no matching saveframe found for their search term
    # and search field
    if cur.rowcount == 0:
        raise RequestError("No matching saveframe found.")
    sf_id, sf_framecode = cur.fetchone()

    # Create the NMR-STAR saveframe
    built_frame = bmrb.Saveframe.from_scratch(sf_framecode)
    built_frame.tag_prefix = "_" + table_name

    # Figure out which tags to display
    tags_to_use, pointer_tags = get_printable_tags(table_name, cur)

    # Get the tag values
    cur.execute('''SELECT * FROM %(table_name)s where "Sf_ID"=%(sf_id)s''',
                {'sf_id': sf_id, 'table_name': wrap_it_up(table_name)})
    tag_vals = cur.fetchone()

    # Add the tags, and optionally add $ if the tag is a pointer
    for pos, tag in enumerate(cur.description):
        if tag.name in tags_to_use:
            if tag.name in pointer_tags:
                built_frame.add_tag(tag.name, "$" + tag_vals[pos])
            else:
                built_frame.add_tag(tag.name, tag_vals[pos])

    # Figure out which loops we might need to insert
    cur.execute('''SELECT tagcategory,min(dictionaryseq) AS seq FROM dict.val_item_tbl
                WHERE originalcategory=%(category)s GROUP BY tagcategory ORDER BY seq''',
                {'category': category})

    # The first result is the saveframe, so drop it
    cur.fetchone()

    # Figure out which loops we might need to add
    loops = [x[0] for x in cur.fetchall()]

    # Add the loops
    for each_loop in loops:

        if configuration['debug']:
            print("Doing loop: %s" % each_loop)

        tags_to_use, pointer_tags = get_printable_tags(each_loop, cur)

        # If there are any tags in the loop to use
        if len(tags_to_use) > 0:
            # Create the loop
            bmrb_loop = bmrb.Loop.from_scratch(category=each_loop)
            bmrb_loop.add_column(tags_to_use)

            # Get the loop data
            to_fetch = ",".join(['"' + x + '"' for x in tags_to_use])
            query = 'SELECT ' + to_fetch
            query += ' FROM %(table_name)s WHERE "Sf_ID" = %(id)s'

            # Determine how to order the data in the loops
            order_tags = []
            for tag in tags_to_use:
                if tag_order["_"+ each_loop + "." + tag] == "Y":
                    order_tags.append(tag)
                    if configuration['debug']:
                        print("Ordering loop %s by %s." % (each_loop, tag))
            if len(order_tags) > 0:
                query += ' ORDER BY %s' % '"' + '","'.join(order_tags) + '"'
            else:
                if configuration['debug']:
                    print("No order in loop: %s" % each_loop)
                # If no explicit order, look for an "ordinal" tag
                for tag in tags_to_use:
                    if "ordinal" in tag or "Ordinal" in tag:
                        if configuration['debug']:
                            print("Found tag to order by (ordinal): %s" % tag)
                        query += ' ORDER BY "%s"' % tag
                        break

            # Perform the query
            cur.execute(query, {"id": sf_id,
                                "table_name":wrap_it_up(each_loop)})
            if configuration['debug']:
                print(cur.query)

            # Add the data
            for row in cur:

                # Make sure to add the "$" if this is a sf_pointer
                row = list(row)
                for pos, tag in enumerate(tags_to_use):
                    if tag in pointer_tags:
                        row[pos] = "$" + row[pos]

                # Add the data
                bmrb_loop.add_data(row)

            if bmrb_loop.data != []:
                built_frame.add_loop(bmrb_loop)

    return built_frame

def create_combined_view():
    """ Create the combined schema from the other three schemas."""

    # Connect as the user that has write privileges
    conn, cur = get_postgres_connection(user="bmrb")

    # Create the new schema if needed
    cur.execute("""SELECT EXISTS(SELECT 1 FROM pg_namespace
                WHERE nspname = 'combined');""")
    if cur.fetchall()[0][0] is False:
        cur.execute("CREATE SCHEMA combined;")
        # TODO: Once we have postgres 9.3 replace the above 3 lines with
        # cur.execute("CREATE SCHEMA IF NOT EXISTS combined;")

    # Get the tables we need to combine
    cur.execute('''SELECT table_name,table_schema FROM information_schema.tables
                WHERE table_catalog = 'bmrbeverything' AND
                (table_schema = 'metabolomics' OR table_schema = 'chemcomps'
                 OR table_schema = 'macromolecules');''')
    rows = cur.fetchall()

    # Figure out how to combine them
    combine_dict = {}
    for row in rows:
        if row[0] in combine_dict:
            combine_dict[row[0]].append(row[1])
        else:
            combine_dict[row[0]] = [row[1]]

    for table_name in combine_dict.keys():
        query = ''
        if len(combine_dict[table_name]) == 1:
            print("Warning. Table from only one schema found.")
        elif len(combine_dict[table_name]) == 2:
            query = '''
CREATE OR REPLACE VIEW combined."%s" AS
select * from %s."%s" t
 union all
select * from %s."%s" tt;''' % (table_name,
                                combine_dict[table_name][0], table_name,
                                combine_dict[table_name][1], table_name)
        elif len(combine_dict[table_name]) == 3:
            query = '''
CREATE OR REPLACE VIEW combined."%s" AS
select * from %s."%s" t
 union all
select * from %s."%s" tt
 union all
select * from %s."%s" ttt;''' % (table_name,
                                 combine_dict[table_name][0], table_name,
                                 combine_dict[table_name][1], table_name,
                                 combine_dict[table_name][2], table_name)

        cur.execute(query)
        print(query)

    cur.execute("GRANT USAGE ON SCHEMA combined to web;")
    cur.execute("GRANT SELECT ON ALL TABLES IN SCHEMA combined TO web;")
    cur.execute("GRANT EXECUTE ON ALL FUNCTIONS IN SCHEMA combined TO web;")

    # Let web see it
    conn.commit()
