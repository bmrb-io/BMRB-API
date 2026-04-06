#!/usr/bin/env python3

""" This module provides methods to service the different query types that are
provided through the REST interface. This is where the real work
is done; restapi.py mainly just calls the methods here and returns the results.
"""
import logging
import os
import zlib
from typing import Union, List, Generator, Tuple, Optional

import pynmrstar
import simplejson as json
from flask import request
from psycopg import sql
from psycopg.errors import ProgrammingError
from redis import StrictRedis

from bmrbapi.exceptions import RequestException, ServerException
from bmrbapi.utils.configuration import configuration
from bmrbapi.utils.connections import PostgresConnection, RedisConnection

# Determine submodules folder
_QUERYMOD_DIR = os.path.dirname(os.path.realpath(__file__))
SUBMODULE_DIR = os.path.join(os.path.dirname(_QUERYMOD_DIR), "submodules")

# Set up logging
logging.basicConfig()

# Cache for dictionary metadata that is static across all entries.
# Populated lazily on first access per process (safe with multiprocessing fork).
_dict_cache = {}


def locate_entry(entry_id: str, r_conn: StrictRedis) -> str:
    """ Determines what the Redis key is for an entry given the database
    provided."""

    if entry_id.startswith("bm"):
        return "metabolomics:entry:%s" % entry_id
    elif entry_id.startswith("chemcomp"):
        return "chemcomps:entry:%s" % entry_id
    elif len(entry_id) == 32:
        entry_loc = "uploaded:entry:%s" % entry_id

        # Update the expiration time if the entry is used
        if r_conn.exists(entry_loc):
            r_conn.expire(entry_loc, configuration['redis']['upload_timeout'])

        return entry_loc
    else:
        return "macromolecules:entry:%s" % entry_id


def get_database_from_entry_id(entry_id: str) -> str:
    """ Returns the appropriate database to inspect based on ID."""

    if entry_id.startswith("bm"):
        return "metabolomics"
    else:
        return "macromolecules"


def get_valid_entries_from_redis(search_ids: Union[str, list],
                                 format_: str = "object",
                                 max_results: int = 500) -> \
        Generator[Tuple[str, Union[bytes, str, dict, pynmrstar.Entry]], None, None]:
    """ Given a list of entries, yield them as the appropriate type as determined by the "format_"
    variable. Throw an exception if any of the provided IDs do not exist.

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

    # Make sure there are not too many entries
    if len(search_ids) > max_results:
        raise RequestException('Too many IDs queried. Please query %s or fewer entries at a time. You attempted to '
                               'query %d IDs.' % (max_results, len(search_ids)))

    # Get the connection to redis if needed
    with RedisConnection() as r_conn:

        # Go through the IDs
        for entry_id in search_ids:

            entry = r_conn.get(locate_entry(entry_id, r_conn=r_conn))

            # See if it is in redis
            if entry:
                # Return the compressed entry
                if format_ == "zlib":
                    yield entry_id, entry

                else:
                    # Uncompress the zlib into serialized JSON
                    entry = zlib.decompress(entry)
                    if format_ == "json":
                        yield entry_id, entry
                    else:
                        # Parse the JSON into python dict
                        entry = json.loads(entry)
                        if format_ == "dict":
                            yield entry_id, entry
                        else:
                            # Parse the dict into object
                            entry = pynmrstar.Entry.from_json(entry)
                            if format_ == "object":
                                yield entry_id, entry
                            else:
                                # Return NMR-STAR
                                if format_ == "nmrstar" or format_ == "rawnmrstar":
                                    yield entry_id, str(entry)

                                # Unknown format
                                else:
                                    raise RequestException("Invalid format: %s." % format_)
            else:
                raise RequestException("Entry '%s' does not exist in the public database." % entry_id, status_code=404)


def get_category_and_tag(tag_name: str) -> List[str]:
    """ Returns the tag category and the tag formatted as needed for DB
    queries. Returns an error if an invalid tag is provided. """

    if tag_name is None:
        raise RequestException("You must specify the tag name.")

    # Note - this is relied on in some queries to prevent SQL injection. Do
    #  not remove it unless you update all functions that use this function.
    if '"' in tag_name:
        raise RequestException('Tags cannot contain a \'"\'.')

    sp = tag_name.split(".")
    if sp[0].startswith("_"):
        sp[0] = sp[0][1:]
    if len(sp) < 2:
        raise RequestException("You must provide a full tag name with category included. For example: "
                               "Entry.Experimental_method_subtype")

    if len(sp) > 2:
        raise RequestException("You provided an invalid tag. NMR-STAR tags only contain one period.")

    return sp


def select(fetch_list: List[str], table: str, where_dict: dict = None, database: str = "macromolecules",
           modifiers: List = None, as_dict: bool = True) -> dict:
    """ Performs a SELECT query constructed from the supplied arguments."""

    # Turn None parameters into the proper empty type
    if where_dict is None:
        where_dict = {}
    if modifiers is None:
        modifiers = []

    # Make sure they aren't trying to inject
    if '"' in table:
        raise RequestException("Invalid 'from' parameter.")

    table_ref = sql.SQL("{}.{}").format(sql.Identifier(database), sql.Identifier(table))
    data_params = []

    # Build SELECT clause
    if len(fetch_list) == 1 and fetch_list[0] == "*":
        if "count" in modifiers:
            select_clause = sql.SQL("count(*)")
        else:
            select_clause = sql.SQL("*")
    else:
        columns = [sql.Identifier(x) for x in fetch_list]
        if "count" in modifiers:
            select_clause = sql.SQL(",").join(
                [sql.SQL("count({})").format(c) for c in columns]
            )
        else:
            select_clause = sql.SQL(",").join(columns)

    query = sql.SQL("SELECT {} FROM {}").format(select_clause, table_ref)

    # Build WHERE clause
    if len(where_dict) > 0:
        where_parts = []
        for key in where_dict:
            if "lower" in modifiers:
                where_parts.append(
                    sql.SQL("regexp_replace(LOWER({}),E'\\n','') LIKE LOWER(%s)").format(sql.Identifier(key))
                )
            else:
                where_parts.append(
                    sql.SQL("regexp_replace({},E'\\n','') LIKE %s").format(sql.Identifier(key))
                )
            data_params.append(where_dict[key].replace("*", "%"))

        query = query + sql.SQL(" WHERE ") + sql.SQL(" AND ").join(where_parts)

    with PostgresConnection() as cur:
        # Do the query
        try:
            cur.execute(query, data_params if data_params else None)
            rows = cur.fetchall()
        except ProgrammingError as error:
            if configuration['debug']:
                raise error
            raise RequestException("Invalid 'from' parameter.")

        # Get the column names from the DB
        col_names = [desc[0] for desc in cur.description]

        if not as_dict:
            return {'data': rows, 'columns': [table + "." + x for x in col_names]}

        # Turn the results into a dictionary
        result = {}

        if "count" in modifiers:
            for pos, search_field in enumerate(fetch_list):
                result[table + "." + search_field] = rows[0][pos]
        else:
            for search_field in col_names:
                result[table + "." + search_field] = []
                s_index = col_names.index(search_field)
                for row in rows:
                    result[table + "." + search_field].append(row[s_index])

        if configuration['debug']:
            result['debug'] = {'query': query.as_string(cur), 'params': data_params}

    return result


def create_chemcomp_from_db(chemcomp: str) -> pynmrstar.Entry:
    """ Create a chem comp entry from the database."""

    # Rebuild the chemcomp and generate the cc_id. This way we can work
    # with the three letter string or the full chemcomp. Also make sure
    # to capitalize it.
    if len(chemcomp) == 3:
        cc_id = chemcomp.upper()
    else:
        cc_id = chemcomp[9:].upper()
    chemcomp = "chem_comp_" + cc_id

    # Connect to DB
    with PostgresConnection() as cur:
        # Create entry
        chemcomp_frame = create_saveframe_from_db("chemcomps", "chem_comp", cc_id, "ID", cur)
        # Set the frame name manually, because in the database it is wrong?
        chemcomp_frame.name = chemcomp
        entity_frame = create_saveframe_from_db("chemcomps", "entity", cc_id, "Nonpolymer_comp_ID", cur)

    ent = pynmrstar.Entry.from_scratch(chemcomp)
    # This is specifically omitted... long story
    try:
        del entity_frame['_Entity_atom_list']
    except ValueError:
        pass

    ent.add_saveframe(entity_frame)
    ent.add_saveframe(chemcomp_frame)

    return ent


def get_entry_id_tag(tag_or_category: str, database: str = "macromolecules") -> str:
    """ Returns the tag that contains the logical Entry ID. This isn't always the Entry_ID tag.

    You should always provide a Postgres cursor if you've already opened one."""

    # Determine if this is a fully qualified tag or just the category
    try:
        tag_category = get_category_and_tag(tag_or_category)[0]
    except RequestException:
        tag_category = tag_or_category.replace(".", "")
        while tag_category.startswith("_"):
            tag_category = tag_category[1:]

    # Chemcomp DB has hardcoded values since chemcomp_id is different from entry ID
    if database == "chemcomps":
        id_tag = {'entity': 'BMRB_code',
                  'entity_comp_index': 'Comp_ID',
                  'chem_comp': 'ID',
                  'chem_comp_descriptor': 'Comp_ID',
                  'chem_comp_identifier': 'Comp_ID',
                  'chem_comp_atom': 'Comp_ID',
                  'chem_comp_bond': 'Comp_ID'}
        try:
            return id_tag[tag_category.lower()]
        except KeyError:
            raise ServerException("Unknown ID tag for tag: %s" % tag_or_category)

    with PostgresConnection() as cur:
        cur.execute("""
SELECT tagfield
  FROM dict.adit_item_tbl
  WHERE entryidflg='Y' AND lower(tagcategory)=lower(%s);""", [tag_category])

        try:
            return cur.fetchone()['tagfield']
        except TypeError:
            raise RequestException("Invalid tag queried, unable to determine entryidflag.")


def get_printable_tags(category: str, cur) -> Tuple[List[str], List[str]]:
    """ Returns a list of the tags that should be printed for the given
    category and a list of tags that are pointers."""

    cache_key = ('printable_tags', category)
    if cache_key in _dict_cache:
        return _dict_cache[cache_key]

    # Figure out the loop tags
    cur.execute('''SELECT a.tagfield,a.internalflag,p.printflag,a.dictionaryseq,a.sfpointerflg
                FROM dict.adit_item_tbl a JOIN dict.validator_printflags p ON p.dictionaryseq = a.dictionaryseq
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

    _dict_cache[cache_key] = (tags_to_use, pointer_tags)
    return tags_to_use, pointer_tags


def create_saveframe_from_db(database: str, category: str, entry_id: str, id_search_field: str,
                             cur) -> Optional[pynmrstar.Saveframe]:
    """ Builds a saveframe from the database. You specify the database:
    (metabolomics, macromolecules, chemcomps, combined), the category of the
    saveframe, the identifier of the saveframe, and the name of the tag that
    we should search for the identifier (within the saveframe's table).

    You can optionally pass a cursor to reuse an existing postgresql
    connection."""

    # Get the list of which tags should be used to order data (cached - same for all entries)
    if 'tag_order' not in _dict_cache:
        cur.execute('''SELECT originaltag,rowindexflg from dict.adit_item_tbl''')
        _dict_cache['tag_order'] = {x['originaltag']: x['rowindexflg'] for x in cur.fetchall()}
    tag_order = _dict_cache['tag_order']

    # Set the search path (needed for unqualified data table references below)
    cur.execute(sql.SQL('SET search_path={}, pg_catalog').format(sql.Identifier(database)))

    # Check if we are allowed to print it (cached per category)
    cat_grp_key = ('cat_grp', category)
    if cat_grp_key not in _dict_cache:
        cur.execute('''SELECT internalflag,printflag FROM dict.cat_grp
                    WHERE sfcategory=%(sf_cat)s ORDER BY groupid''',
                    {'sf_cat': category})
        _dict_cache[cat_grp_key] = cur.fetchone()
    internalflag, printflag = _dict_cache[cat_grp_key]

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

    # Get table name from category name (cached per category)
    table_key = ('table_name', category)
    if table_key not in _dict_cache:
        cur.execute("""SELECT DISTINCT tagcategory FROM dict.adit_item_tbl
                    WHERE originalcategory=%(category)s AND loopflag<>'Y'""",
                    {"category": category})
        _dict_cache[table_key] = cur.fetchone()['tagcategory']
    table_name = _dict_cache[table_key]

    # Figure out which tags to display (cached per table)
    tags_to_use, pointer_tags = get_printable_tags(table_name, cur)

    # Fetch the saveframe row — single query replaces the former Sf_ID lookup + separate tag value fetch
    cur.execute(
        sql.SQL('SELECT * FROM {} WHERE {} = %s ORDER BY "Sf_ID"').format(
            sql.Identifier(table_name), sql.Identifier(id_search_field)
        ), [entry_id])
    tag_vals = cur.fetchone()

    # There is no matching saveframe found for their search term and search field
    if tag_vals is None:
        raise RequestException("No matching saveframe found.")

    sf_id = tag_vals['Sf_ID']
    sf_framecode = tag_vals['Sf_framecode']
    # Save column metadata now — cached get_printable_tags won't touch the cursor,
    # but on first call per worker it would overwrite cur.description
    col_description = cur.description

    # Create the NMR-STAR saveframe
    built_frame = pynmrstar.Saveframe.from_scratch(sf_framecode)
    built_frame.tag_prefix = "_" + table_name

    # Add the tags, and optionally add $ if the tag is a pointer
    for pos, tag in enumerate(col_description):
        if tag.name in tags_to_use:
            if tag.name in pointer_tags:
                built_frame.add_tag(tag.name, "$" + tag_vals[pos])
            else:
                built_frame.add_tag(tag.name, tag_vals[pos])

    # Figure out which loops we might need to insert (cached per category)
    loops_key = ('loops', category)
    if loops_key not in _dict_cache:
        cur.execute('''SELECT tagcategory,min(dictionaryseq) AS seq FROM dict.adit_item_tbl
                    WHERE originalcategory=%(category)s GROUP BY tagcategory ORDER BY seq''',
                    {'category': category})
        # The first result is the saveframe, so drop it
        cur.fetchone()
        _dict_cache[loops_key] = [x['tagcategory'] for x in cur.fetchall()]
    loops = _dict_cache[loops_key]

    # Add the loops
    for each_loop in loops:
        tags_to_use, pointer_tags = get_printable_tags(each_loop, cur)

        # If there are any tags in the loop to use
        if len(tags_to_use) > 0:
            # Create the loop
            bmrb_loop = pynmrstar.Loop.from_scratch(category=each_loop)
            bmrb_loop.add_tag(tags_to_use)

            # Get the loop data
            to_fetch_sql = sql.SQL(",").join([sql.Identifier(x) for x in tags_to_use])
            query = sql.SQL('SELECT {} FROM {} WHERE "Sf_ID" = %s').format(
                to_fetch_sql, sql.Identifier(each_loop))

            # Determine how to order the data in the loops
            order_tags = []
            for tag in tags_to_use:
                if tag_order["_" + each_loop + "." + tag] == "Y":
                    order_tags.append(tag)
                    if configuration['debug']:
                        print("Ordering loop %s by %s." % (each_loop, tag))
            if len(order_tags) > 0:
                query = query + sql.SQL(' ORDER BY {}').format(
                    sql.SQL(',').join([sql.Identifier(t) for t in order_tags]))
            else:
                if configuration['debug']:
                    print("No order in loop: %s" % each_loop)
                # If no explicit order, look for an "ordinal" tag
                for tag in tags_to_use:
                    if "ordinal" in tag or "Ordinal" in tag:
                        if configuration['debug']:
                            print("Found tag to order by (ordinal): %s" % tag)
                        query = query + sql.SQL(' ORDER BY {}').format(sql.Identifier(tag))
                        break

            # Perform the query
            cur.execute(query, [sf_id])
            if configuration['debug']:
                print(query.as_string(cur))

            # Add the data
            for row in cur:

                # Make sure to add the "$" if this is a sf_pointer
                row = list(row)
                for pos, tag in enumerate(tags_to_use):
                    if tag in pointer_tags:
                        row[pos] = "$" + row[pos]

                # Add the data
                bmrb_loop.add_data(row)

            if bmrb_loop.data:
                built_frame.add_loop(bmrb_loop)

    return built_frame


def create_combined_view() -> None:
    """ Create the combined schema from the other three schemas."""

    # Connect as the user that has write privileges
    psql = PostgresConnection(write_access=True)
    with psql as cur:

        # Create the new schema if needed
        cur.execute("CREATE SCHEMA IF NOT EXISTS combined;")

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
                logging.warning("Table from only one schema found.")
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

        cur.execute("GRANT USAGE ON SCHEMA combined to web;")
        cur.execute("GRANT SELECT ON ALL TABLES IN SCHEMA combined TO web;")
        cur.execute("GRANT EXECUTE ON ALL FUNCTIONS IN SCHEMA combined TO web;")

        # Let web see it
        psql.commit()


# Helper methods
def get_db(default: str = "macromolecules", valid_list: List[str] = None) -> str:
    """ Make sure the DB specified is valid. """

    if not valid_list:
        valid_list = ["metabolomics", "macromolecules", "combined", "chemcomps"]

    database = request.args.get('database', default)

    if database not in valid_list:
        raise RequestException("Invalid database: %s." % database)

    return database


def check_local_ip() -> bool:
    """ Checks if the given IP is a local user."""

    for local_address in configuration['local-ips']:
        if request.remote_addr.startswith(local_address):
            return True

    return False
