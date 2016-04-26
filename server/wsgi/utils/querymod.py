#!/usr/bin/python

import sys
import json
import redis
import logging
import psycopg2
from cPickle import loads, dumps
from redis.sentinel import Sentinel
from psycopg2.extensions import AsIs
from jsonrpc.exceptions import JSONRPCDispatchException as JSONException

# Load bmrb locally
import bmrb

# Load the configuration file
configuration = json.loads(open("../../../api_config.json", "r").read())
# Set up logging
logging.basicConfig()

# Method to connect to REDIS and load the valid IDS
def get_REDIS_connection():
    # Connect to redis
    try:
        # Figure out where we should connect
        sentinel = Sentinel(configuration['redis']['sentinels'], socket_timeout=0.5)
        redis_host, redis_port = sentinel.discover_master('tarpon_master')
        r = redis.StrictRedis(host=redis_host, port=redis_port, password=configuration['redis']['password'])
        if not int(r.get("ready")):
            logging.warning("Serviced request during update.")
    except redis.exceptions.ConnectionError:
        raise JSONException(-32603, 'Could not connect to database server.')

    return r

# Helper method that yields only whatever valid IDs were loaded from REDIS
def get_valid_entries_from_REDIS(search_ids):

    # Wrap the IDs in a list if necessary
    if not isinstance(search_ids, list):
        search_ids = [search_ids]

    # Make sure there are not too many entries
    if len(search_ids) > 500:
        raise JSONException(-32602, 'Too many IDs queried. Please query 500 or fewer entries at a time. You attempted to query %d IDs.' % len(search_ids))

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
        entry = r.get(entry_id)
        if entry:
            entry = loads(entry)
            if entry:
                yield entry

# Returns all valid entry IDs
def list_entries(**kwargs):
    return get_REDIS_connection().lrange("loaded", 0, -1)

# Get one unpickled entry
def get_pickled_entry(entry_id):
    return get_REDIS_connection().get(entry_id)

# Return the tags
def get_tags(**kwargs):

    # Get the valid IDs and REDIS connection
    search_tags = process_STAR_query(kwargs)
    result = {}

    # Go through the IDs
    for entry in get_valid_entries_from_REDIS(kwargs['ids']):
        result[entry.bmrb_id] = entry.getTags(search_tags)

    return result

# Return the loops
def get_loops(**kwargs):

    # Get the valid IDs and REDIS connection
    loop_categories = process_STAR_query(kwargs)
    result = {}

    # Go through the IDs
    for entry in get_valid_entries_from_REDIS(kwargs['ids']):
        result[entry.bmrb_id] = {}
        for loop_category in loop_categories:
            matches = entry.getLoopsByCategory(loop_category)
            if kwargs.get('raw', False):
                result[entry.bmrb_id][loop_category] = [str(x) for x in matches]
            else:
                result[entry.bmrb_id][loop_category] = [x.getJSON() for x in matches]

    return result

# Return the saveframes
def get_saveframes(**kwargs):

    # Get the valid IDs and REDIS connection
    saveframe_categories = process_STAR_query(kwargs)
    result = {}

    # Go through the IDs
    for entry in get_valid_entries_from_REDIS(kwargs['ids']):
        result[entry.bmrb_id] = {}
        for saveframe_category in saveframe_categories:
            matches = entry.getSaveframesByCategory(saveframe_category)
            if kwargs.get('raw', False):
                result[entry.bmrb_id][saveframe_category] = [str(x) for x in matches]
            else:
                result[entry.bmrb_id][saveframe_category] = [x.getJSON() for x in matches]
    return result

# Return the full entry
def get_entries(**kwargs):

    # Get the valid IDs and REDIS connection
    ignore = process_STAR_query(kwargs)
    result = {}

    # Go through the IDs
    for entry in get_valid_entries_from_REDIS(kwargs['ids']):
        if kwargs.get('raw', False):
            result[entry.bmrb_id] = str(entry)
        else:
            result[entry.bmrb_id] = entry.getJSON()

    return result

# Properly quote things for postgres
def wrap_it_up(item):
    return AsIs('"' + item + '"')

def get_fields_by_fields(fetch_list, table, where_dict={}, database="bmrb",
                        modifiers=[], as_hash=True):

    # Errors connecting will be handled upstream
    conn = psycopg2.connect(user=configuration['postgres']['user'],
                                host=configuration['postgres']['host'], database=database)

    cur = conn.cursor()

    # Prepare the query
    if len(fetch_list) == 1 and fetch_list[0] == "*":
        pass
        parameters = []
    else:
        parameters = [wrap_it_up(x) for x in fetch_list]
    query = "SELECT "
    if "count" in modifiers:
        query += "count(" + "),count(".join(["%s"]*len(fetch_list)) + ') from "' + table + '"'
    else:
        if len(fetch_list) == 1 and fetch_list[0] == "*":
            query += "*" + ' from "' + table + '"'
        else:
            query += ",".join(["%s"]*len(fetch_list)) + ' from "' + table + '"'
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

    if not "count" in modifiers:
        query += ' ORDER BY "Entry_ID"'
        # Order the parameters as ints if they are normal BMRB IDS
        if database == "bmrb":
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

    # Make sure they have IDS
    if not "ids" in params:
        raise JSONException(-32602, 'You must specify one or more entry IDs with the "ids" parameter.')

    # Set the keys to the empty list if not specified
    if not 'keys' in params:
        params['keys'] = []

    # Wrap the key in a list if necessary
    if not isinstance(params['keys'], list):
        params['keys'] = [params['keys']]

    return params['keys']

# Process a JSON request
def process_select(**params):

    # Get the database name
    database = params.get("database", "macromolecule")
    database = {'macromolecule':'bmrb', 'metabolomics':'metabolomics', 'both':'both'}.get(database,None)
    if database == "both":
        raise JSONException(-32602, 'Merged database not yet available.')
    if database != "bmrb" and database != "metabolomics":
        raise JSONException(-32602, "Invalid database specified.")

    # Okay, now we need to go through each query and get the results
    if not isinstance(params['query'], list):
        params['query'] = [params['query']]

    result_list = []

    #select distinct cast(T0."ID" as integer) as "Entry.ID" from "Entry" T0 join "Citation" T1 on T0."ID"=T1."Entry_ID" join "Chem_comp" T2 on T0."ID"=T2."Entry_ID" where T0."ID" ~* '1' and T1."Title" ~* 'T' and T2."Entry_ID" ~* '1' order by cast(T0."ID" as integer)

    # Build the amalgamation of queries
    for each_query in params['query']:

        # For one query:
        each_query['select'] = each_query.get("select", ["Entry_ID"])
        if not isinstance(each_query['select'], list):
            each_query['select'] = [each_query['select']]
        # We need the ID to join if they are doing multiple queries
        if len(params['query']) > 1:
            each_query['select'].append("Entry_ID")
        if not "from" in each_query:
            raise JSONException(-32602, 'You must specify which table to query with the "from" parameter.')
        if not "hash" in each_query:
            each_query['hash'] = True

        # Get the query modifiers
        each_query['modifiers'] = each_query.get("modifiers",[])
        if not isinstance(each_query['modifiers'], list):
            each_query['modifiers'] = [each_query['modifiers']]

        each_query['where'] = each_query.get("where", {})

        if len(params['query']) > 1:
            result_list.append(get_fields_by_fields(each_query['select'], each_query['from'], where_dict=each_query['where'], database=database, modifiers=each_query['modifiers'], as_hash=False))
        else:
            return get_fields_by_fields(each_query['select'], each_query['from'], where_dict=each_query['where'], database=database, modifiers=each_query['modifiers'], as_hash=each_query['hash'])

    return result_list

    # Synchronized list generation
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
