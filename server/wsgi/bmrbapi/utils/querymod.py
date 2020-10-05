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
from psycopg2 import ProgrammingError
from psycopg2.extensions import AsIs
from psycopg2.extras import DictCursor
from redis import StrictRedis

from bmrbapi.exceptions import RequestException, ServerException
from bmrbapi.utils.configuration import configuration
from bmrbapi.utils.connections import PostgresConnection, RedisConnection

# Determine submodules folder
_QUERYMOD_DIR = os.path.dirname(os.path.realpath(__file__))
SUBMODULE_DIR = os.path.join(os.path.dirname(_QUERYMOD_DIR), "submodules")

# Set up logging
logging.basicConfig()


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


def wrap_it_up(item: all) -> AsIs:
    """ Quote items in a way that postgres accepts and that doesn't allow
    SQL injection."""
    return AsIs('"' + item + '"')


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

    # Make sure they aren't trying to inject (parameterized queries are safe while
    # this is not, but there is no way to parametrize a table name...)
    if '"' in table:
        raise RequestException("Invalid 'from' parameter.")

    # Prepare the query
    if len(fetch_list) == 1 and fetch_list[0] == "*":
        parameters = []
    else:
        parameters = [wrap_it_up(x) for x in fetch_list]
    query = "SELECT "
    if "count" in modifiers:
        # Build the 'select * from *' part of the query
        query += "count(" + "),count(".join(["%s"] * len(fetch_list))
        query += ') from %s."%s"' % (database, table)
    else:
        if len(fetch_list) == 1 and fetch_list[0] == "*":
            query += '* from %s."%s"' % (database, table)
        else:
            # Build the 'select * from *' part of the query
            query += ",".join(["%s"] * len(fetch_list))
            query += ' from %s."%s"' % (database, table)

    if len(where_dict) > 0:
        query += " WHERE"
        need_and = False

        for key in where_dict:
            if need_and:
                query += " AND"
            if "lower" in modifiers:
                query += " regexp_replace(LOWER(%s),'\n','') LIKE LOWER(%s)"
            else:
                query += " regexp_replace(%s,'\n','') LIKE %s"
            parameters.extend([wrap_it_up(key), where_dict[key].replace("*", "%")])
            need_and = True

    # TODO: build ordering in based on dictionary
    #    if "count" not in modifiers:
    #        query += ' ORDER BY "Entry_ID"'
    #        # Order the parameters as ints if they are normal BMRB IDS
    #        if database == "macromolecules":
    #            query += "::int "

    query += ';'

    with PostgresConnection() as cur:
        # Do the query
        try:
            cur.execute(query, parameters)
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
            result['debug'] = cur.query

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
    chemcomp = "chemcomp_" + cc_id

    # Connect to DB
    with PostgresConnection() as cur:
        # Create entry
        chemcomp_frame = create_saveframe_from_db("chemcomps", "chem_comp", cc_id, "ID", cur)
        entity_frame = create_saveframe_from_db("chemcomps", "entity", cc_id, "Nonpolymer_comp_ID", cur)

    ent = pynmrstar.Entry.from_scratch(chemcomp)
    # This is specifically omitted... long story
    try:
        del entity_frame['_Entity_atom_list']
    except KeyError:
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
            return cur.fetchone()[0]
        except TypeError:
            raise RequestException("Invalid tag queried, unable to determine entryidflag.")


def get_printable_tags(category: str, cur: DictCursor) -> Tuple[List[str], List[str]]:
    """ Returns a list of the tags that should be printed for the given
    category and a list of tags that are pointers."""

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

    return tags_to_use, pointer_tags


def create_saveframe_from_db(database: str, category: str, entry_id: str, id_search_field: str,
                             cur: DictCursor) -> Optional[pynmrstar.Saveframe]:
    """ Builds a saveframe from the database. You specify the database:
    (metabolomics, macromolecules, chemcomps, combined), the category of the
    saveframe, the identifier of the saveframe, and the name of the tag that
    we should search for the identifier (within the saveframe's table).

    You can optionally pass a cursor to reuse an existing postgresql
    connection."""

    # Look up information about the tags to use later
    # cur.execute('''SELECT adit_item_tbl.originaltag,adit_item_tbl.internalflag,
    # printflag,adit_item_tbl.dictionaryseq,rowindexflg FROM dict.adit_item_tbl,
    # dict.adit_item_tbl WHERE adit_item_tbl.originaltag=
    # adit_item_tbl.originaltag''')

    # Get the list of which tags should be used to order data
    cur.execute('''SELECT originaltag,rowindexflg from dict.adit_item_tbl''')
    tag_order = {x[0]: x[1] for x in cur.fetchall()}

    # Set the search path
    cur.execute('''SET search_path=%(path)s, pg_catalog;''', {'path': database})

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
    cur.execute("""SELECT DISTINCT tagcategory FROM dict.adit_item_tbl
                WHERE originalcategory=%(category)s AND loopflag<>'Y'""",
                {"category": category})
    table_name = cur.fetchone()[0]

    logging.debug("Will look in table: %s", table_name)

    # Get the sf_id for later
    cur.execute('''SELECT "Sf_ID","Sf_framecode" FROM %(table_name)s
                WHERE %(search_field)s=%(id)s ORDER BY "Sf_ID"''',
                {"id": entry_id, 'table_name': wrap_it_up(table_name),
                 "search_field": wrap_it_up(id_search_field)})

    # There is no matching saveframe found for their search term
    # and search field
    if cur.rowcount == 0:
        raise RequestException("No matching saveframe found.")
    sf_id, sf_framecode = cur.fetchone()

    # Create the NMR-STAR saveframe
    built_frame = pynmrstar.Saveframe.from_scratch(sf_framecode)
    built_frame.tag_prefix = "_" + table_name

    # Figure out which tags to display
    tags_to_use, pointer_tags = get_printable_tags(table_name, cur)

    # Get the tag values
    cur.execute('''SELECT * FROM %(table_name)s WHERE "Sf_ID"=%(sf_id)s''',
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
    cur.execute('''SELECT tagcategory,min(dictionaryseq) AS seq FROM dict.adit_item_tbl
                WHERE originalcategory=%(category)s GROUP BY tagcategory ORDER BY seq''',
                {'category': category})

    # The first result is the saveframe, so drop it
    cur.fetchone()

    # Figure out which loops we might need to add
    loops = [x[0] for x in cur.fetchall()]

    # Add the loops
    for each_loop in loops:

        logging.debug("Doing loop: %s", each_loop)

        tags_to_use, pointer_tags = get_printable_tags(each_loop, cur)

        # If there are any tags in the loop to use
        if len(tags_to_use) > 0:
            # Create the loop
            bmrb_loop = pynmrstar.Loop.from_scratch(category=each_loop)
            bmrb_loop.add_tag(tags_to_use)

            # Get the loop data
            to_fetch = ",".join(['"' + x + '"' for x in tags_to_use])
            query = 'SELECT ' + to_fetch
            query += ' FROM %(table_name)s WHERE "Sf_ID" = %(id)s'

            # Determine how to order the data in the loops
            order_tags = []
            for tag in tags_to_use:
                if tag_order["_" + each_loop + "." + tag] == "Y":
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
                                "table_name": wrap_it_up(each_loop)})
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
