#!/usr/bin/python

""" This module provides methods to service the different query types that are
provided through the REST and JSON-RPC interfaces. This is where the real work
is done; jsonapi.wsgi and restapi.wsgi mainly just call the methods here and
return the results."""

import json
import zlib
import logging

import psycopg2
from psycopg2.extensions import AsIs
import redis
from redis.sentinel import Sentinel

# Local imports
import bmrb
from jsonrpc.exceptions import JSONRPCDispatchException as JSONException

# Load the configuration file
configuration = json.loads(open("../../../api_config.json", "r").read())
# Set up logging
logging.basicConfig()

def get_REDIS_connection():
    """ Figures out where the master redis instance is (and other paramaters
    needed to connect like which database to use), and opens a connection
    to it. It passes back that connection object."""

    # Connect to redis
    try:
        # Figure out where we should connect
        sentinel = Sentinel(configuration['redis']['sentinels'],
                            socket_timeout=0.5)
        redis_host, redis_port = sentinel.discover_master('tarpon_master')

        # Get the redis instance
        r = redis.StrictRedis(host=redis_host,
                              port=redis_port,
                              password=configuration['redis']['password'],
                              db=configuration['redis']['db'])

        # If the redis instance is being updated during the request then
        #  write a warning to the log
        if not int(r.get("ready")):
            logging.warning("Serviced request during update.")

    # Raise an exception if we cannot connect to the database server
    except redis.exceptions.ConnectionError:
        raise JSONException(-32603, 'Could not connect to database server.')

    return r

def get_valid_entries_from_REDIS(search_ids, raw=False):
    """ Given a list of entries, yield the subset that exist in the database
    as PyNMR-STAR objects. If raw is set to True then yield the entries in
    unserialized JSON form."""

    # Wrap the IDs in a list if necessary
    if not isinstance(search_ids, list):
        search_ids = [search_ids]

    # Make sure there are not too many entries
    if len(search_ids) > 500:
        raise JSONException(-32602, 'Too many IDs queried. Please query 500 or '
                                    'fewer entries at a time. You attempted to '
                                    'query %d IDs.' % len(search_ids))

    # Get the connection to REDIS
    r = get_REDIS_connection()
    all_ids = r.lrange("loaded", 0, -1)

    valid_ids = []

    # Figure out which IDs in the query exist in the database
    for request_id in [str(x) for x in search_ids]:
        if request_id in all_ids:
            valid_ids.append(request_id)

    # Go through the IDs
    for entry_id in valid_ids:

        # See if it is in REDIS
        entry_json = r.get(entry_id)
        if entry_json:
            entry_json = zlib.decompress(entry_json)

            # If they just want the JSON dictionary
            if raw:
                yield json.loads(entry_json)
            else:
                try:
                    yield bmrb.entry.fromJSON(json.loads(entry_json))
                except ValueError:
                    pass

def get_raw_entry(entry_id):
    """ Get one serialized entry. """

    entry = get_REDIS_connection().get(entry_id)

    # See if the entry is in the database
    if entry is None:
        return json.dumps({"error": "No such entry: %s" % entry_id})
    else:
        return '{"%s": ' % entry_id + zlib.decompress(entry) + "}"

def list_entries(**kwargs):
    """ Returns all valid entry IDs by default. If a database is specified than
    only entries from that database are returned. """

    entry_list = get_REDIS_connection().lrange("loaded", 0, -1)

    db = kwargs.get("database", None)
    if db:
        if db == "metabolomics":
            entry_list = [x for x in entry_list if x.startswith("bm")]
        if db == "macromolecules":
            entry_list = [x for x in entry_list if not x.startswith("bm")]
        if db == "chemcomps":
            entry_list = [x for x in entry_list if not x.startswith("chem")]

    return entry_list

def get_tags(**kwargs):
    """ Returns results for the queried tags."""

    # Get the valid IDs and REDIS connection
    search_tags = process_STAR_query(kwargs)
    result = {}

    # Go through the IDs
    for entry in get_valid_entries_from_REDIS(kwargs['ids']):
        result[entry.bmrb_id] = entry.getTags(search_tags)

    return result

def get_loops(**kwargs):
    """ Returns the matching loops."""

    # Get the valid IDs and REDIS connection
    loop_categories = process_STAR_query(kwargs)
    result = {}

    # Go through the IDs
    for entry in get_valid_entries_from_REDIS(kwargs['ids']):
        result[entry.bmrb_id] = {}
        for loop_category in loop_categories:
            matches = entry.getLoopsByCategory(loop_category)
            if kwargs.get('raw', False):
                matching_loops = [str(x) for x in matches]
            else:
                matching_loops = [x.getJSON(serialize=False) for x in matches]
            result[entry.bmrb_id][loop_category] = matching_loops

    return result

def get_saveframes(**kwargs):
    """ Returns the matching saveframes."""

    # Get the valid IDs and REDIS connection
    saveframe_categories = process_STAR_query(kwargs)
    result = {}

    # Go through the IDs
    for entry in get_valid_entries_from_REDIS(kwargs['ids']):
        result[entry.bmrb_id] = {}
        for saveframe_category in saveframe_categories:
            matches = entry.getSaveframesByCategory(saveframe_category)
            if kwargs.get('raw', False):
                matching_frames = [str(x) for x in matches]
            else:
                matching_frames = [x.getJSON(serialize=False) for x in matches]
            result[entry.bmrb_id][saveframe_category] = matching_frames
    return result

def get_entries(**kwargs):
    """ Returns the full entries."""

    # Check their paramters before proceeding
    process_STAR_query(kwargs)
    result = {}

    # Go through the IDs
    raw = kwargs.get('raw', False)
    for entry in get_valid_entries_from_REDIS(kwargs['ids'], raw=raw):
        result[entry.bmrb_id] = entry.getJSON(serialize=False)

    return result

def wrap_it_up(item):
    """ Quote items in a way that postgres accepts and that doesn't allow
    SQL injection."""
    return AsIs('"' + item + '"')

def get_fields_by_fields(fetch_list, table, where_dict=None,
                         schema="macromolecules", modifiers=None, as_hash=True):
    """ Performs a SELECT query constructed from the supplied arguments."""

    # Turn None parameters into the proper empty type
    if where_dict is None:
        where_dict = {}
    if modifiers is None:
        modifiers = []

    # Errors connecting will be handled upstream
    conn = psycopg2.connect(user=configuration['postgres']['user'],
                            host=configuration['postgres']['host'],
                            database=configuration['postgres']['database'])

    cur = conn.cursor()

    # Prepare the query
    if len(fetch_list) == 1 and fetch_list[0] == "*":
        parameters = []
    else:
        parameters = [wrap_it_up(x) for x in fetch_list]
    query = "SELECT "
    if "count" in modifiers:
        # Build the 'select * from *' part of the query
        query += "count(" + "),count(".join(["%s"]*len(fetch_list))
        query += ') from %s."%s"' % (schema, table)
    else:
        if len(fetch_list) == 1 and fetch_list[0] == "*":
            query += '* from %s."%s"' % (schema, table)
        else:
            # Build the 'select * from *' part of the query
            query += ",".join(["%s"]*len(fetch_list))
            query += ' from %s."%s"' % (schema, table)

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

    if "count" not in modifiers:
        query += ' ORDER BY "Entry_ID"'
        # Order the parameters as ints if they are normal BMRB IDS
        if schema == "macromolecule":
            query += "::int "

    query += ';'

    # Do the query
    cur.execute(query, parameters)
    rows = cur.fetchall()

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
        raise JSONException(-32602, 'You must specify one or more entry IDs '
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
    schema = params.get("database", "macromolecules")

    if schema == "all":
        raise JSONException(-32602, 'Merged database not yet available.')
    if schema not in ["chemcomps", "macromolecules", "metabolomics", "dict"]:
        raise JSONException(-32602, "Invalid database specified.")

    # Okay, now we need to go through each query and get the results
    if not isinstance(params['query'], list):
        params['query'] = [params['query']]

    result_list = []

    select_example = """select distinct cast(T0."ID" as integer) as "Entry.ID"
    from "Entry" T0 join "Citation" T1 on T0."ID"=T1."Entry_ID" join "Chem_comp"
    T2 on T0."ID"=T2."Entry_ID" where T0."ID" ~* '1' and T1."Title" ~* 'T'
    and T2."Entry_ID" ~* '1' order by cast(T0."ID" as integer)"""

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
            raise JSONException(-32602, 'You must specify which table to query '
                                        'with the "from" parameter.')
        if "hash" not in each_query:
            each_query['hash'] = True

        # Get the query modifiers
        each_query['modifiers'] = each_query.get("modifiers", [])
        if not isinstance(each_query['modifiers'], list):
            each_query['modifiers'] = [each_query['modifiers']]

        each_query['where'] = each_query.get("where", {})

        if len(params['query']) > 1:
            # If there are multiple queries then add their results to the list
            cur_res = get_fields_by_fields(each_query['select'],
                                           each_query['from'],
                                           where_dict=each_query['where'],
                                           schema=schema,
                                           modifiers=each_query['modifiers'],
                                           as_hash=False)
            result_list.append(cur_res)
        else:
            # If there is only one query just return it
            return get_fields_by_fields(each_query['select'],
                                        each_query['from'],
                                        where_dict=each_query['where'],
                                        schema=schema,
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
