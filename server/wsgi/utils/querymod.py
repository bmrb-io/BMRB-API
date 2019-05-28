#!/usr/bin/env python3

""" This module provides methods to service the different query types that are
provided through the REST interface. This is where the real work
is done; restapi.py mainly just calls the methods here and returns the results.
"""

import os
import zlib
import logging
import textwrap
import subprocess
from hashlib import md5
from decimal import Decimal
from time import time as unix_time
from sys import maxsize as max_integer
from tempfile import NamedTemporaryFile
from typing import Dict, Union, Any, List
from urllib.parse import quote as urlquote

from flask import url_for
import simplejson as json

import psycopg2
from psycopg2.extensions import AsIs
from psycopg2.extras import execute_values, DictCursor
from psycopg2 import ProgrammingError
import redis
from redis.sentinel import Sentinel

# Local imports
import pynmrstar

# Module level defines
__all__ = ['create_chemcomp_from_db', 'create_saveframe_from_db', 'get_tags',
           'get_loops', 'get_saveframes_by_category', 'get_saveframes_by_name',
           'get_entries', 'get_redis_connection', 'get_postgres_connection',
           'get_status', 'list_entries', 'select', 'configuration', 'get_enumerations',
           'store_uploaded_entry']

_METHODS = ['list_entries', 'entry/', 'entry/ENTRY_ID/validate',
            'entry/ENTRY_ID/experiments', 'entry/ENTRY_ID/software', 'status',
            'software/', 'software/package/', 'instant', 'enumerations/',
            'search/', 'search/chemical_shifts', 'search/fasta/',
            'search/get_all_values_for_tag/', 'search/get_id_by_tag_value/',
            'search/multiple_shift_search', 'search/get_bmrb_ids_from_pdb_id/',
            'search/get_pdb_ids_from_bmrb_id/', 'search/get_bmrb_data_from_pdb_id/',
            'molprobity/PDB_ID/oneline', 'molprobity/PDB_ID/residue']


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
        """ Converts the payload to a dictionary."""
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
        """ Converts the payload to a dictionary."""
        rv = dict(self.payload or ())
        rv['error'] = self.message
        return rv


_QUERYMOD_DIR = os.path.dirname(os.path.realpath(__file__))

# Load the configuration file
config_loc = os.path.join(_QUERYMOD_DIR, "..", "..", "..", "..", "api_config.json")
if not os.path.isfile(config_loc):
    config_loc = os.path.join(_QUERYMOD_DIR, "..", "configuration.json")
configuration = json.loads(open(config_loc, "r").read())

# Load local configuration overrides
config_loc = os.path.join(_QUERYMOD_DIR, "..", "..", "..", "api_config.json")
if os.path.isfile(config_loc):
    config_overrides = json.loads(open(config_loc, "r").read())
    for config_param in config_overrides:
        configuration[config_param] = config_overrides[config_param]

# Determine submodules folder
_SUBMODULE_DIR = os.path.join(os.path.dirname(_QUERYMOD_DIR), "submodules")
_FASTA_LOCATION = os.path.join(_SUBMODULE_DIR, "fasta36", "bin", "fasta36")

# Set up logging
logging.basicConfig()


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
                            port=configuration['postgres']['port'],
                            dictionary_cursor=False):
    """ Returns a connection to postgres and a cursor."""

    # Errors connecting will be handled upstream
    if dictionary_cursor:
        conn = psycopg2.connect(user=user, host=host, database=database,
                                port=port, cursor_factory=DictCursor)
    else:
        conn = psycopg2.connect(user=user, host=host, database=database,
                                port=port)
    cur = conn.cursor()

    return conn, cur


def set_database(cursor, database):
    """ Sets the search path to the database the query is for."""

    if database == "combined":
        raise RequestError("Combined database not implemented yet.")

    if database not in ["metabolomics", "macromolecules", "chemcomps"]:
        raise RequestError("Invalid database: %s." % database)

    cursor.execute('SET search_path=%s;', [database])


def get_redis_connection(db=None):
    """ Figures out where the master redis instance is (and other parameters
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
            # If in debug, use debug database
            if configuration['debug']:
                db = 1
            else:
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
                                        max_results=max_integer)


def get_valid_entries_from_redis(search_ids, format_="object", max_results=500, r_conn=None):
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

    # Make sure there are not too many entries
    if len(search_ids) > max_results:
        raise RequestError('Too many IDs queried. Please query %s '
                           'or fewer entries at a time. You attempted to '
                           'query %d IDs.' % (max_results, len(search_ids)))

    # Get the connection to redis if needed
    if r_conn is None:
        r_conn = get_redis_connection()

    # Go through the IDs
    for entry_id in search_ids:

        entry = r_conn.get(locate_entry(entry_id, r_conn=r_conn))

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
                        entry = pynmrstar.Entry.from_json(entry)
                        if format_ == "object":
                            yield (entry_id, entry)
                        else:
                            # Return NMR-STAR
                            if format_ == "nmrstar" or format_ == "rawnmrstar":
                                yield (entry_id, str(entry))

                            # Unknown format
                            else:
                                raise RequestError("Invalid format: %s." % format_)


def store_uploaded_entry(request):
    """ Store an uploaded NMR-STAR file in the database."""

    uploaded_data = request.data

    if not uploaded_data:
        raise RequestError("No data uploaded. Please post the "
                           "NMR-STAR file as the request body.")

    if request.content_type == "application/json":
        try:
            parsed_star = pynmrstar.Entry.from_json(uploaded_data)
        except (ValueError, TypeError) as e:
            raise RequestError("Invalid uploaded JSON NMR-STAR data."
                               " Exception: %s" % str(e))
    else:
        try:
            parsed_star = pynmrstar.Entry.from_string(uploaded_data)
        except ValueError as e:
            raise RequestError("Invalid uploaded NMR-STAR file."
                               " Exception: %s" % str(e))

    key = md5(uploaded_data).digest().encode("hex")

    r = get_redis_connection()
    r.setex("uploaded:entry:%s" % key, configuration['redis']['upload_timeout'],
            zlib.compress(parsed_star.get_json()))

    return {"entry_id": key,
            "expiration": unix_time() + configuration['redis']['upload_timeout']}


def panav_parser(panav_text):
    """ Parses the PANAV data into something jsonify-able."""

    if type(panav_text) == bytes:
        panav_text = panav_text.decode()

    lines = panav_text.split("\n")

    # Initialize the result dictionary
    result: Dict[str, Union[str, list, dict]] = {'offsets': {},
                                                 'deviants': [],
                                                 'suspicious': [],
                                                 'text': panav_text}

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
        result['offsets']['CO'] = float(lines[1].split(" ")[-1].replace("ppm", ""))
        result['offsets']['CA'] = float(lines[2].split(" ")[-1].replace("ppm", ""))
        result['offsets']['CB'] = float(lines[3].split(" ")[-1].replace("ppm", ""))
        result['offsets']['N'] = float(lines[4].split(" ")[-1].replace("ppm", ""))

    # Figure out how many deviant and suspicious shifts were detected
    num_deviants = int(lines[deviant_line].rstrip().split(" ")[-1])
    num_suspicious = int(lines[suspicious_line + num_deviants].rstrip().split(" ")[-1])
    suspicious_line += num_deviants + 1
    deviant_line += 1

    # Get the deviants
    for deviant in lines[deviant_line:deviant_line + num_deviants]:
        res_num, res, atom, shift = deviant.strip().split(" ")
        result['deviants'].append({"residue_number": res_num, "residue_name": res,
                                   "atom": atom, "chemical_shift_value": shift})

    # Get the suspicious shifts
    for suspicious in lines[suspicious_line:suspicious_line + num_suspicious]:
        res_num, res, atom, shift = suspicious.strip().split(" ")
        result['suspicious'].append({"residue_number": res_num, "residue_name": res,
                                     "atom": atom, "chemical_shift_value": shift})

    # Return the result dictionary
    return result


def get_citation(entry_id, format_="python"):
    """ Returns the citation for the entry. """

    # Error if invalid
    if format_ not in ["python", "json-ld", "text", "bibtex"]:
        raise RequestError("Invalid format specified. Please choose from the "
                           "following formats: %s" % str(["json-ld", "text", "bibtex"]))

    ent_ret_id, entry = next(get_valid_entries_from_redis(entry_id))

    # First lets get all the values we need, later we will format them

    def get_tag(saveframe, tag):
        tag = saveframe.get_tag(tag)
        if not tag:
            return ""
        else:
            return tag[0]

    # Authors and citations
    authors = []
    citations = []
    citation_title, citation_journal, citation_volume_issue, citation_pagination, citation_year = '', '', '', '', ''

    for citation_frame in entry.get_saveframes_by_category("citations"):
        if get_tag(citation_frame, "Class") == "entry citation":
            cl = citation_frame["_Citation_author"]

            # Get the journal information
            citation_journal = get_tag(citation_frame, "Journal_abbrev")
            issue = get_tag(citation_frame, "Journal_issue")
            if issue and issue != ".":
                issue = "(%s)" % issue
            else:
                issue = ""
            volume = get_tag(citation_frame, "Journal_volume")
            if not volume or volume == ".":
                volume = ""
            citation_volume_issue = "%s%s" % (volume, issue)
            citation_year = get_tag(citation_frame, "Year")
            citation_pagination = "%s-%s" % (get_tag(citation_frame, "Page_first"),
                                             get_tag(citation_frame, "Page_last"))
            citation_title = get_tag(citation_frame, "Title").strip()

            # Authors
            for row in cl.get_tag(["Given_name", "Family_name", "Middle_initials"]):
                auth = {"@type": "Person", "givenName": row[0], "familyName": row[1]}
                if row[2] != ".":
                    auth["additionalName"] = row[2]
                authors.append(auth)

            # Citations
            doi = get_tag(citation_frame, "DOI")
            if doi and doi != ".":
                citations.append({"@type": "ScholarlyArticle",
                                  "@id": "https://doi.org/" + doi,
                                  "headline": get_tag(citation_frame, "Title"),
                                  "datePublished": get_tag(citation_frame, "Year")})

    # Figure out last update day, version, and original release
    orig_release, last_update, version = None, None, 1
    for row in entry.get_loops_by_category("Release")[0].get_tag(["Release_number",
                                                                  "Date"]):
        if row[0] == "1":
            orig_release = row[1]
        if int(row[0]) >= version:
            last_update = row[1]
            version = int(row[0])

    # Title
    title = entry.get_tag("Entry.Title")[0].rstrip()

    # DOI string
    doi = "10.13018/BMR%s" % ent_ret_id
    if ent_ret_id.startswith("bmse") or ent_ret_id.startswith("bmst"):
        doi = "10.13018/%s" % ent_ret_id.upper()

    if format_ == "json-ld" or format_ == "python":
        res = {"@context": "http://schema.org",
               "@type": "Dataset",
               "@id": "https://doi.org/10.13018/%s" % doi,
               "publisher": "Biological Magnetic Resonance Bank",
               "datePublished": orig_release,
               "dateModified": last_update,
               "version": "v%s" % version,
               "name": title,
               "author": authors}

        if len(citations) > 0:
            res["citation"] = citations

        if format_ == "json-ld":
            return json.dumps(res)
        else:
            return res

    if format_ == "bibtex":
        ret_string = """@misc{%(entry_id)s,
 author = {%(author)s},
 publisher = {Biological Magnetic Resonance Bank},
 title = {%(title)s},
 year = {%(year)s},
 month = {%(month)s},
 doi = {%(doi)s},
 howpublished = {https://doi.org/%(doi)s}
 url = {https://doi.org/%(doi)s}
}"""

        ret_keys = {"entry_id": ent_ret_id, "title": title,
                    "year": orig_release[0:4], "month": orig_release[5:7],
                    "doi": doi,
                    "author": " and ".join([x["familyName"] + ", " + x["givenName"] for x in authors])}

        return ret_string % ret_keys

    if format_ == "text":

        names = []
        for x in authors:
            name = x["familyName"] + ", " + x["givenName"][0] + "."
            if "additionalName" in x:
                name += x["additionalName"]
            names.append(name)

        text_dict = {"entry_id": entry_id, "title": title,
                     "citation_title": citation_title,
                     "citation_journal": citation_journal,
                     "citation_volume_issue": citation_volume_issue,
                     "citation_pagination": citation_pagination,
                     "citation_year": citation_year,
                     "author": ", ".join(names),
                     "doi": doi}

        if citation_journal:
            return """BMRB ID: %(entry_id)s
%(author)s
%(citation_title)s
%(citation_journal)s %(citation_volume_issue)s pp. %(citation_pagination)s (%(citation_year)s) doi: %(doi)s""" % \
                   text_dict
        else:
            return """BMRB ID: %(entry_id)s %(author)s %(title)s doi: %(doi)s""" % text_dict


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
            star_file.file.write(str(entry[1]).encode())
            star_file.flush()

            avs_location = os.path.join(_SUBMODULE_DIR, "avs/validate_assignments_31.pl")
            res = subprocess.check_output([avs_location, entry[0], "-nitrogen", "-fmean",
                                           "-aromatic", "-std", "-anomalous", "-suspicious",
                                           "-star_output", star_file.name])

            error_loop = pynmrstar.Entry.from_string(res.decode())
            error_loop = error_loop.get_loops_by_category("_AVS_analysis_r")[0]
            error_loop = error_loop.filter(["Assembly_ID", "Entity_assembly_ID",
                                            "Entity_ID", "Comp_index_ID",
                                            "Comp_ID",
                                            "Comp_overall_assignment_score",
                                            "Comp_typing_score",
                                            "Comp_SRO_score",
                                            "Comp_1H_shifts_analysis_status",
                                            "Comp_13C_shifts_analysis_status",
                                            "Comp_15N_shifts_analysis_status"])
            error_loop.category = "AVS_analysis"

            # Modify the chemical shift loops with the new data
            shift_lists = entry[1].get_loops_by_category("atom_chem_shift")
            for loop in shift_lists:
                loop.add_tag(["AVS_analysis_status", "PANAV_analysis_status"])
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
                chem_shifts.file.write(str(cs_loop).encode())
                chem_shifts.flush()

                panav_location = os.path.join(_SUBMODULE_DIR, "panav/panav.jar")
                try:
                    res = subprocess.check_output(["java", "-cp", panav_location,
                                                   "CLI", "-f", "star", "-i",
                                                   chem_shifts.name],
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


def get_tags(**kwargs):
    """ Returns results for the queried tags."""

    # Get the valid IDs and redis connection
    search_tags = process_nmrstar_query(kwargs)
    result = {}

    # Check the validity of the tags
    for tag in search_tags:
        if "." not in tag:
            raise RequestError("You must provide the tag category to call this method at the entry level. For example, "
                               "use 'Entry.Title' rather than 'Title'.")

    # Go through the IDs
    for entry in get_valid_entries_from_redis(kwargs['ids']):
        try:
            result[entry[0]] = entry[1].get_tags(search_tags)
        # They requested a tag that doesn't exist
        except ValueError as error:
            raise RequestError(str(error))

    return result


def get_status():
    """ Return some statistics about the server."""

    r = get_redis_connection()
    stats: Dict[str, Union[List[str], Dict[Union[int, str], Any]]] = {}
    for key in ['metabolomics', 'macromolecules', 'chemcomps', 'combined']:
        stats[key] = {}
        for k, v in r.hgetall("%s:meta" % key).items():
            k = k.decode()
            v = v.decode()
            stats[key][k] = v
        for skey in stats[key]:
            if skey == "update_time":
                stats[key][skey] = float(stats[key][skey])
            else:
                stats[key][skey] = int(stats[key][skey])

    pg = get_postgres_connection()[1]
    for key in ['metabolomics', 'macromolecules']:
        sql = '''SELECT reltuples FROM pg_class
                 WHERE oid = '%s."Atom_chem_shift"'::regclass;''' % key
        pg.execute(sql)
        stats[key]['num_chemical_shifts'] = int(pg.fetchone()[0])

    # Add the available methods
    stats['methods'] = _METHODS
    stats['version'] = subprocess.check_output(["git", "describe", "--abbrev=0"]).strip()

    return stats


def get_loops(**kwargs):
    """ Returns the matching loops."""

    # Get the valid IDs and redis connection
    loop_categories = process_nmrstar_query(kwargs)
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
        cur = get_postgres_connection(dictionary_cursor=True)[1]

    if not tag.startswith("_"):
        tag = "_" + tag

    # Get the list of which tags should be used to order data
    cur.execute('''
SELECT it.itemenumclosedflg,it.enumeratedflg,array_agg(enum.val) as values
 FROM dict.adit_item_tbl as it
 LEFT JOIN dict.enumerations as enum on enum.seq = it.dictionaryseq
WHERE originaltag=%s
GROUP BY it.itemenumclosedflg,it.enumeratedflg;''', [tag])
    p_res = cur.fetchone()
    if not p_res:
        raise RequestError("Invalid tag specified.")

    # Generate the result dictionary
    result = {'values': p_res['values']}
    if p_res['itemenumclosedflg'] == "Y":
        result['type'] = "enumerations"
    elif p_res['enumeratedflg'] == "Y":
        result['type'] = "common"
    else:
        result['type'] = None

    # Be able to search through enumerations based on the term argument
    if term is not None:
        new_result = []
        for val in result['values']:
            if val and val.startswith(term):
                new_result.append({"value": val, "label": val})
        return new_result

    return result


def multiple_peak_search(peaks, database="metabolomics"):
    """ Parses the JSON request and does a search against multiple peaks."""

    cur = get_postgres_connection()[1]
    set_database(cur, database)

    sql = '''
SELECT atom_shift."Entry_ID",atom_shift."Assigned_chem_shift_list_ID"::text,
  array_agg(DISTINCT atom_shift."Val"::numeric),ent.title,ent.link
FROM "Atom_chem_shift" as atom_shift
LEFT JOIN web.instant_cache as ent
  ON ent.id = atom_shift."Entry_ID"
WHERE '''
    terms = []

    fpeaks = []
    peak = None
    try:
        for peak in peaks:
            fpeaks.append(float(peak))
    except ValueError:
        raise RequestError("Invalid peak specified. All peaks must be numbers. Invalid peak: '%s'" % peak)

    peaks = sorted(fpeaks)

    for peak in peaks:
        sql += '''
((atom_shift."Val"::float < %s  AND atom_shift."Val"::float > %s AND
 (atom_shift."Atom_type" = 'C' OR atom_shift."Atom_type" = 'N'))
 OR
 (atom_shift."Val"::float < %s  AND atom_shift."Val"::float > %s AND atom_shift."Atom_type" = 'H')) OR '''
        terms.append(peak + .2)
        terms.append(peak - .2)
        terms.append(peak + .01)
        terms.append(peak - .01)

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
        result['data'].append({'Entry_ID': entry[0],
                               'Assigned_chem_shift_list_ID': entry[1],
                               'Val': entry[2],
                               'Title': title,
                               'Link': entry[4]})

    # Convert the search to decimal
    peaks = [Decimal(x) for x in peaks]

    def get_closest(collection, number):
        """ Returns the closest number from a list of numbers. """
        return min(collection, key=lambda _: abs(_ - number))

    def get_sort_key(res):
        """ Returns the sort key. """

        key = 0

        # Add the difference of all the shifts
        for item in res['Val']:
            key += abs(get_closest(peaks, item) - item)
        res['Combined_offset'] = round(key, 3)

        # Determine how many of the queried peaks were matched
        num_match = 0
        for check_peak in peaks:
            closest = get_closest(res['Val'], check_peak)
            if abs(check_peak - closest) < .2:
                num_match += 1
        res['Peaks_matched'] = num_match

        return -num_match, key, res['Entry_ID']

    result['data'] = sorted(result['data'], key=get_sort_key)

    return result


def chemical_shift_search_1d(shift_val=None, threshold=.03, atom_type=None,
                             atom_id=None, comp_id=None, conditions=False,
                             database="macromolecules"):
    """ Searches for a given chemical shift. """

    cur = get_postgres_connection()[1]
    set_database(cur, database)

    try:
        threshold = float(threshold)
    except ValueError:
        raise RequestError("Invalid threshold.")

    sql = '''
SELECT cs."Entry_ID","Entity_ID"::integer,"Comp_index_ID"::integer,"Comp_ID","Atom_ID","Atom_type",
  cs."Val"::numeric,cs."Val_err"::numeric,"Ambiguity_code","Assigned_chem_shift_list_ID"::integer
FROM "Atom_chem_shift" as cs
WHERE
'''

    if conditions:
        sql = '''
SELECT cs."Entry_ID","Entity_ID"::integer,"Comp_index_ID"::integer,"Comp_ID","Atom_ID","Atom_type",
  cs."Val"::numeric,cs."Val_err"::numeric,"Ambiguity_code","Assigned_chem_shift_list_ID"::integer,
  web.convert_to_numeric(ph."Val") as ph,web.convert_to_numeric(temp."Val") as temp
FROM "Atom_chem_shift" as cs
LEFT JOIN "Assigned_chem_shift_list" as csf
  ON csf."ID"=cs."Assigned_chem_shift_list_ID" AND csf."Entry_ID"=cs."Entry_ID"
LEFT JOIN "Sample_condition_variable" AS ph
  ON csf."Sample_condition_list_ID"=ph."Sample_condition_list_ID" AND ph."Entry_ID"=cs."Entry_ID" AND ph."Type"='pH'
LEFT JOIN "Sample_condition_variable" AS temp
  ON csf."Sample_condition_list_ID"=temp."Sample_condition_list_ID" AND temp."Entry_ID"=cs."Entry_ID" AND 
     temp."Type"='temperature' AND temp."Val_units"='K'
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

    # Do the query
    cur.execute(sql, args)

    result = {}

    # Send query string if in debug mode
    if configuration['debug']:
        result['debug'] = cur.query

    result['columns'] = ["Atom_chem_shift." + desc[0] for desc in cur.description]

    if conditions:
        result['columns'][-2] = 'Sample_conditions.pH'
        result['columns'][-1] = 'Sample_conditions.Temperature_K'

    result['data'] = cur.fetchall()
    return result


def get_molprobity_data(pdb_id, residues=None):
    """ Returns the molprobity data."""

    pdb_id = pdb_id.lower()
    cur = get_postgres_connection()[1]

    if residues is None:
        sql = '''SELECT * FROM molprobity.oneline where pdb = %s'''
        terms = [pdb_id]
    else:
        terms = [pdb_id]
        if not residues:
            sql = '''SELECT * FROM molprobity.residue where pdb = %s;'''
        else:
            sql = '''SELECT * FROM molprobity.residue where pdb = %s AND ('''
            for item in residues:
                sql += " pdb_residue_no = %s OR "
                terms.append(item)
            sql += " 1=2) ORDER BY model, pdb_residue_no"

    cur.execute(sql, terms)

    res = {"columns": [desc[0] for desc in cur.description],
           "data": cur.fetchall()}

    if configuration['debug']:
        res['debug'] = cur.query

    return res


def get_entry_software(entry_id):
    """ Returns the software used for a given entry. """

    database = get_database_from_entry_id(entry_id)

    cur = get_postgres_connection()[1]
    set_database(cur, database)

    cur.execute('''
SELECT "Software"."Name", "Software"."Version", task."Task" as "Task", vendor."Name" as "Vendor Name"
FROM "Software"
   LEFT JOIN "Vendor" as vendor ON "Software"."Entry_ID"=vendor."Entry_ID" AND "Software"."ID"=vendor."Software_ID"
   LEFT JOIN "Task" as task ON "Software"."Entry_ID"=task."Entry_ID" AND "Software"."ID"=task."Software_ID"
WHERE "Software"."Entry_ID"=%s;''', [entry_id])

    column_names = [desc[0] for desc in cur.description]
    return {"columns": column_names, "data": cur.fetchall()}


def get_schema(version=None):
    """ Return the schema from Redis. """

    r = get_redis_connection()
    if not version:
        version = r.get('schema_version')
    try:
        schema = json.loads(zlib.decompress(r.get("schema:%s" % version)))
    except TypeError:
        raise RequestError("Invalid schema version.")

    return schema


def get_software_entries(software_name, database="macromolecules"):
    """ Returns the entries assosciated with a given piece of software. """

    cur = get_postgres_connection()[1]
    set_database(cur, database)

    # Get the list of which tags should be used to order data
    cur.execute('''
SELECT "Software"."Entry_ID","Software"."Name","Software"."Version",vendor."Name" as "Vendor Name",
  vendor."Electronic_address" as "e-mail",task."Task" as "Task"
FROM "Software"
  LEFT JOIN "Vendor" as vendor
    ON "Software"."Entry_ID"=vendor."Entry_ID" AND "Software"."ID"=vendor."Software_ID"
  LEFT JOIN "Task" as task
    ON "Software"."Entry_ID"=task."Entry_ID" AND "Software"."ID"=task."Software_ID"
WHERE lower("Software"."Name") like lower(%s);''', ["%" + software_name + "%"])

    column_names = [desc[0] for desc in cur.description]
    return {"columns": column_names, "data": cur.fetchall()}


def get_software_summary(database="macromolecules"):
    """ Returns all software packages from the DB. """

    cur = get_postgres_connection()[1]
    set_database(cur, database)

    # Get the list of which tags should be used to order data
    cur.execute('''
SELECT "Software"."Name","Software"."Version",task."Task" as "Task",vendor."Name" as "Vendor Name"
FROM "Software"
  LEFT JOIN "Vendor" as vendor
    ON "Software"."Entry_ID"=vendor."Entry_ID" AND "Software"."ID"=vendor."Software_ID"
  LEFT JOIN "Task" as task
    ON "Software"."Entry_ID"=task."Entry_ID" AND "Software"."ID"=task."Software_ID";''')

    column_names = [desc[0] for desc in cur.description]
    return {"columns": column_names, "data": cur.fetchall()}


def do_sql_mods(conn=None, cur=None, sql_file=None):
    """ Make sure functions we need are saved in the DB. """

    # Re-use existing connection
    if not (conn and cur):
        conn, cur = get_postgres_connection(user=configuration['postgres']['reload_user'])

    if sql_file is None:
        sql_file = os.path.join(os.path.dirname(os.path.realpath(__file__)),
                                "sql", "initialize.sql")
    else:
        sql_file = os.path.join(os.path.dirname(os.path.realpath(__file__)),
                                "sql", sql_file)

    cur.execute(open(sql_file, "r").read())
    conn.commit()


def create_timedomain_table():
    """Creates the time domain links table."""

    def get_dir_size(start_path='.'):
        total_size = 0
        for dir_path, dir_names, file_names in os.walk(start_path):
            for f in file_names:
                fp = os.path.join(dir_path, f)
                total_size += os.path.getsize(fp)
        return total_size

    def get_data_sets(path):
        sets = 0
        last_set = ""
        for f in os.listdir(path):
            if os.path.isdir(os.path.join(path, f)):
                sets += 1
                last_set = os.path.join(path, f)
        if sets == 1:
            child_sets = get_data_sets(last_set)
            if child_sets > 1:
                return child_sets
        return sets

    conn, cur = get_postgres_connection()
    cur.execute('''
DROP TABLE IF EXISTS web.timedomain_data;
CREATE TABLE web.timedomain_data (
 bmrbid text PRIMARY KEY,
 size numeric,
 sets numeric);''')

    def td_data_getter():
        td_dir = configuration['timedomain_directory']
        for x in os.listdir(td_dir):
            x: str = x
            entry_id = int("".join([_ for _ in x if _.isdigit()]))
            yield (entry_id, get_dir_size(os.path.join(td_dir, x)), get_data_sets(os.path.join(td_dir, x)))

    execute_values(cur, '''INSERT INTO web.timedomain_data(bmrbid, size, sets) VALUES %s;''', td_data_getter())
    conn.commit()


def create_csrosetta_table(csrosetta_sqlite_file):
    """Creates the CS-Rosetta links table."""

    import sqlite3

    c = sqlite3.connect(csrosetta_sqlite_file).cursor()
    entries = c.execute('''
SELECT key, bmrbid, rosetta_version, csrosetta_version, rmsd_lowest
  FROM entries;''').fetchall()

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
        logging.debug("Inserting %s", entry[0])
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
        logging.debug("Inserting %s", entry[0])
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


def fasta_search(query, a_type="polymer", e_val=None):
    """Performs a FASTA search on the specified query in the BMRB database."""

    # Make sure the type is valid
    if a_type not in ["polymer", "rna", "dna"]:
        raise RequestError("Invalid search type: %s" % a_type)
    a_type = {'polymer': 'polypeptide(L)', 'rna': 'polyribonucleotide',
              'dna': 'polydeoxyribonucleotide'}[a_type]

    if not os.path.isfile(_FASTA_LOCATION):
        raise ServerError("Unable to perform FASTA search. Server improperly installed.")

    cur = get_postgres_connection()[1]
    set_database(cur, "macromolecules")
    cur.execute('''
SELECT ROW_NUMBER() OVER (ORDER BY 1) AS id, entity."Entry_ID",entity."ID",
  regexp_replace(entity."Polymer_seq_one_letter_code", E'[\\n\\r]+', '', 'g' ),
  replace(regexp_replace(entry."Title", E'[\\n\\r]+', ' ', 'g' ), '  ', ' ')
FROM "Entity" as entity
  LEFT JOIN "Entry" as entry
  ON entity."Entry_ID" = entry."Entry_ID"
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
        fargs = [_FASTA_LOCATION, "-m", "8"]
        if e_val:
            fargs.extend(["-E", e_val])
        fargs.extend([fasta_file.name, sequence_file.name])

        # Run FASTA
        res = subprocess.check_output(fargs, stderr=subprocess.STDOUT).decode()

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

    return results


def get_experiments(entry):
    """ Returns the experiments for this entry. """

    cur = get_postgres_connection(dictionary_cursor=True)[1]
    set_database(cur, get_database_from_entry_id(entry))

    # First get the sample components
    sql = '''
SELECT "Mol_common_name", "Isotopic_labeling", "Type", "Concentration_val", "Concentration_val_units", "Sample_ID"
FROM "Sample_component"
  WHERE "Entry_ID" = %s'''
    cur.execute(sql, [entry])
    stored_results = cur.fetchall()

    # Then get all of the other information
    sql = '''
SELECT me."Entry_ID", me."Sample_ID", me."ID", ns."Manufacturer",ns."Model",me."Name" as experiment_name,
  ns."Field_strength", array_agg(ef."Name") as name, array_agg(ef."Type") as type,
  array_agg(ef."Directory_path") as directory_path, array_agg(ef."Details") as details, ph."Val" as ph,
  temp."Val" as temp
FROM "Experiment" as me
  LEFT JOIN "Experiment_file" as ef
    ON me."ID" = ef."Experiment_ID" AND me."Entry_ID" = ef."Entry_ID"
  LEFT JOIN "NMR_spectrometer" as ns
    ON ns."Entry_ID" = me."Entry_ID" and ns."ID" = me."NMR_spectrometer_ID"

  LEFT JOIN "Sample_condition_variable" AS ph
    ON me."Sample_condition_list_ID"=ph."Sample_condition_list_ID" AND ph."Entry_ID"=me."Entry_ID" AND ph."Type"='pH'
  LEFT JOIN "Sample_condition_variable" AS temp
    ON me."Sample_condition_list_ID"=temp."Sample_condition_list_ID" AND temp."Entry_ID"=me."Entry_ID" AND
       temp."Type"='temperature' AND temp."Val_units"='K'

WHERE me."Entry_ID" = %s
GROUP BY me."Entry_ID", me."Name", me."ID", ns."Manufacturer", ns."Model",ns."Field_strength", ph."Val",
         temp."Val", me."Sample_ID"
ORDER BY me."Entry_ID" ASC, me."ID" ASC;'''
    cur.execute(sql, [entry])

    results = []
    for row in cur:

        data = []
        if row['name'][0]:
            for x, item in enumerate(row['directory_path']):
                data.append({'type': row['type'][x], 'description': row['details'][x],
                             'url': "ftp://ftp.bmrb.wisc.edu/pub/bmrb/metabolomics/entry_directories/%s/%s/%s" % (
                                 row['Entry_ID'], row['directory_path'][x], row['name'][x])})

        tmp_res = {'Name': row['experiment_name'],
                   'Experiment_ID': row['ID'],
                   'Sample_condition_variable': {'ph': row['ph'],
                                                 'temperature': row['temp']},
                   'NMR_spectrometer': {'Manufacturer': row['Manufacturer'],
                                        'Model': row['Model'],
                                        'Field_strength': row['Field_strength']
                                        },
                   'Experiment_file': data,
                   'Sample_component': []}
        for component in stored_results:
            if component['Sample_ID'] == row['Sample_ID']:
                smp = {'Mol_common_name': component['Mol_common_name'],
                       'Isotopic_labeling': component['Isotopic_labeling'],
                       'Type': component['Type'],
                       'Concentration_val': component['Concentration_val'],
                       'Concentration_val_units': component['Concentration_val_units']}
                tmp_res['Sample_component'].append(smp)

        results.append(tmp_res)

    if configuration['debug']:
        results.append(cur.query)

    return results


def get_instant_search(term, database):
    """ Does an instant search and returns results. """

    cur = get_postgres_connection(dictionary_cursor=True)[1]

    if database == "metabolomics":
        instant_query_one = '''
SELECT instant_cache.id,title,citations,authors,link,sub_date,ms.formula,ms.inchi,ms.smiles,
  ms.average_mass,ms.molecular_weight,ms.monoisotopic_mass
FROM web.instant_cache
LEFT JOIN web.metabolomics_summary as ms
  ON instant_cache.id = ms.id
WHERE tsv @@ plainto_tsquery(%s) AND is_metab = 'True' and ms.id IS NOT NULL
ORDER BY instant_cache.id=%s DESC, is_metab ASC, sub_date DESC, ts_rank_cd(tsv, plainto_tsquery(%s)) DESC;'''

        instant_query_two = """
SELECT set_limit(.5);
SELECT DISTINCT on (id) term,termname,'1'::int as sml,tt.id,title,citations,authors,link,sub_date,is_metab,
  NULL as "formula", NULL as "inchi", NULL as "smiles", NULL as "average_mass", NULL as "molecular_weight",
  NULL as "monoisotopic_mass"
FROM web.instant_cache
  LEFT JOIN web.instant_extra_search_terms as tt
  ON instant_cache.id=tt.id
  WHERE tt.identical_term @@ plainto_tsquery(%s)
UNION
SELECT * from (
SELECT DISTINCT on (id) term,termname,similarity(tt.term, %s) as sml,tt.id,title,citations,authors,link,sub_date,
  is_metab,ms.formula,ms.inchi,ms.smiles,ms.average_mass,ms.molecular_weight,ms.monoisotopic_mass FROM web.instant_cache
  LEFT JOIN web.instant_extra_search_terms as tt
    ON instant_cache.id=tt.id
  LEFT JOIN web.metabolomics_summary as ms
    ON instant_cache.id = ms.id
  WHERE tt.term %% %s AND tt.identical_term IS NULL and ms.id IS NOT NULL
  ORDER BY id, similarity(tt.term, %s) DESC) as y
WHERE is_metab = 'True'"""

    elif database == "macromolecules":
        instant_query_one = '''
SELECT id,title,citations,authors,link,sub_date FROM web.instant_cache
WHERE tsv @@ plainto_tsquery(%s) AND is_metab = 'False'
ORDER BY id=%s DESC, is_metab ASC, sub_date DESC, ts_rank_cd(tsv, plainto_tsquery(%s)) DESC;'''

        instant_query_two = """
SELECT set_limit(.5);
SELECT DISTINCT on (id) term,termname,'1'::int as sml,tt.id,title,citations,authors,link,sub_date,is_metab
  FROM web.instant_cache
    LEFT JOIN web.instant_extra_search_terms as tt
    ON instant_cache.id=tt.id
    WHERE tt.identical_term @@ plainto_tsquery(%s)
UNION
SELECT * from (
SELECT DISTINCT on (id) term,termname,similarity(tt.term, %s) as sml,tt.id,title,citations,authors,
  link,sub_date,is_metab
  FROM web.instant_cache
    LEFT JOIN web.instant_extra_search_terms as tt
    ON instant_cache.id=tt.id
    WHERE tt.term %% %s AND tt.identical_term IS NULL
    ORDER BY id, similarity(tt.term, %s) DESC) as y
    WHERE is_metab = 'False'
    ORDER BY sml DESC LIMIT 75;"""

    else:
        instant_query_one = '''
SELECT id,title,citations,authors,link,sub_date FROM web.instant_cache
WHERE tsv @@ plainto_tsquery(%s)
ORDER BY id=%s DESC, is_metab ASC, sub_date DESC, ts_rank_cd(tsv, plainto_tsquery(%s)) DESC;'''

        instant_query_two = """
SELECT set_limit(.5);
SELECT DISTINCT on (id) term,termname,'1'::int as sml,tt.id,title,citations,authors,link,sub_date,is_metab
  FROM web.instant_cache
    LEFT JOIN web.instant_extra_search_terms as tt
    ON instant_cache.id=tt.id
    WHERE tt.identical_term @@ plainto_tsquery(%s)
UNION
SELECT * from (
SELECT DISTINCT on (id) term,termname,similarity(tt.term, %s) as sml,tt.id,title,citations,authors,
  link,sub_date,is_metab
  FROM web.instant_cache
    LEFT JOIN web.instant_extra_search_terms as tt
    ON instant_cache.id=tt.id
    WHERE tt.term %% %s AND tt.identical_term IS NULL
    ORDER BY id, similarity(tt.term, %s) DESC) as y
    ORDER BY sml DESC LIMIT 75;"""

    try:
        cur.execute(instant_query_one, [term, term, term])
    except ProgrammingError:
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
    except ProgrammingError:
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

    return result


def get_saveframes_by_category(**kwargs):
    """ Returns the matching saveframes."""

    # Get the valid IDs and redis connection
    saveframe_categories = process_nmrstar_query(kwargs)
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


def get_saveframes_by_name(**kwargs):
    """ Returns the matching saveframes."""

    # Get the valid IDs and redis connection
    saveframe_names = process_nmrstar_query(kwargs)
    result = {}

    # Go through the IDs
    for entry in get_valid_entries_from_redis(kwargs['ids']):
        result[entry[0]] = {}
        for saveframe_name in saveframe_names:
            try:
                sf = entry[1].get_saveframe_by_name(saveframe_name)
                if kwargs.get('format', "json") == "nmrstar":
                    result[entry[0]][saveframe_name] = str(sf)
                else:
                    result[entry[0]][saveframe_name] = sf.get_json(serialize=False)
            except KeyError:
                continue

    return result


def get_entries(**kwargs):
    """ Returns the full entries."""

    # Check their parameters before proceeding
    process_nmrstar_query(kwargs)
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


def get_category_and_tag(tag_name):
    """ Returns the tag category and the tag formatted as needed for DB
    queries. Returns an error if an invalid tag is provided. """

    if tag_name is None:
        raise RequestError("You must specify the tag name.")

    # Note - this is relied on in some queries to prevent SQL injection. Do
    #  not remove it unless you update all functions that use this function.
    if '"' in tag_name:
        raise RequestError('Tags cannot contain a \'"\'.')

    sp = tag_name.split(".")
    if sp[0].startswith("_"):
        sp[0] = sp[0][1:]
    if len(sp) < 2:
        raise RequestError("You must provide a full tag name with "
                           "category included. For example: "
                           "Entry.Experimental_method_subtype")

    if len(sp) > 2:
        raise RequestError("You provided an invalid tag. NMR-STAR tags only "
                           "contain one period.")

    return sp


def get_all_values_for_tag(tag_name, database):
    """ Returns all the values for a given tag by entry ID as a dictionary. """

    params = get_category_and_tag(tag_name)
    cur = get_postgres_connection()[1]
    set_database(cur, database)

    # Use Entry_ID normally, but occasionally use ID depending on the context
    id_field = get_entry_id_tag(tag_name, database, cur=cur)

    query = '''SELECT "%s", array_agg(%%s) from "%s" GROUP BY "%s";'''
    query = query % (id_field, params[0], id_field)
    try:
        cur.execute(query, [wrap_it_up(params[1])])
    except psycopg2.ProgrammingError as e:
        sp = str(e).split('\n')
        if len(sp) > 3:
            if sp[3].strip().startswith("HINT:  Perhaps you meant to reference the column"):
                raise RequestError("Tag not found. Did you mean the tag: '%s'?" %
                                   sp[3].split('"')[1])

        raise RequestError("Tag not found.")

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


def select(fetch_list, table, where_dict=None, database="macromolecules",
           modifiers=None, as_hash=True, cur=None):
    """ Performs a SELECT query constructed from the supplied arguments."""

    # Turn None parameters into the proper empty type
    if where_dict is None:
        where_dict = {}
    if modifiers is None:
        modifiers = []

    # Make sure they aren't trying to inject (parameterized queries are safe while
    # this is not, but there is no way to parametrize a table name...)
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

    # Do the query
    try:
        cur.execute(query, parameters)
        rows = cur.fetchall()
    except psycopg2.ProgrammingError as error:
        if configuration['debug']:
            raise error
        raise RequestError("Invalid 'from' parameter.")

    # Get the column names from the DB
    col_names = [desc[0] for desc in cur.description]

    if not as_hash:
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


def process_nmrstar_query(params):
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
    ent = pynmrstar.Entry.from_scratch(chemcomp)
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


def get_pdb_ids_from_bmrb_id(bmrb_id):
    """ Returns the associated PDB IDs for a BMRB ID. """

    cur = get_postgres_connection()[1]

    query = '''
SELECT pdb_id, 'Exact' AS link_type, null AS comment
  FROM web.pdb_link
  WHERE bmrb_id LIKE %s
UNION
SELECT "Database_accession_code", 'Author Provided', "Relationship"
  FROM macromolecules."Related_entries"
  WHERE "Entry_ID" LIKE %s AND "Database_name" = 'PDB'
    AND "Relationship" != 'Exact'
UNION
SELECT "Accession_code", 'BLAST Match', "Entry_details"
  FROM macromolecules."Entity_db_link"
  WHERE "Entry_ID" LIKE %s AND "Database_code" = 'PDB'
UNION
SELECT "Accession_code", 'Assembly DB Link', "Entry_details"
  FROM macromolecules."Assembly_db_link"
  WHERE "Entry_ID" LIKE %s AND "Database_code" = 'PDB';'''

    terms = [bmrb_id, bmrb_id, bmrb_id, bmrb_id]
    cur.execute(query, terms)

    return [{"pdb_id": x[0], "match_type": x[1], "comment": x[2]}
            for x in cur.fetchall()]


def get_bmrb_ids_from_pdb_id(pdb_id):
    """ Returns the associated BMRB IDs for a PDB ID. """

    cur = get_postgres_connection()[1]

    query = '''
    SELECT bmrb_id, array_agg(link_type) from 
(SELECT bmrb_id, 'Exact' AS link_type, null as comment
  FROM web.pdb_link
  WHERE pdb_id LIKE %s
UNION
SELECT "Entry_ID", 'Author Provided', "Relationship"
  FROM macromolecules."Related_entries"
  WHERE "Database_accession_code" LIKE %s AND "Database_name" = 'PDB'
    AND "Relationship" != 'Exact'
UNION
SELECT "Entry_ID", 'BLAST Match', "Entry_details"
  FROM macromolecules."Entity_db_link"
  WHERE "Accession_code" LIKE %s AND "Database_code" = 'PDB'
UNION
SELECT "Entry_ID", 'Assembly DB Link', "Entry_details"
  FROM macromolecules."Assembly_db_link"
  WHERE "Accession_code" LIKE %s AND "Database_code" = 'PDB') as sub
GROUP BY bmrb_id;'''

    pdb_id = pdb_id.upper()
    terms = [pdb_id, pdb_id, pdb_id, pdb_id]
    cur.execute(query, terms)

    result = []
    for x in cur.fetchall():
        result.append({"bmrb_id": x[0], "match_types": x[1]})

    return result


def get_extra_data_available(bmrb_id, cur=None, r_conn=None):
    """ Returns any additional data associated with the entry. For example:

    Time domain, residual dipolar couplings, pKa values, etc."""

    # Set up the DB cursor
    if cur is None:
        cur = get_postgres_connection(dictionary_cursor=True)[1]
    set_database(cur, get_database_from_entry_id(bmrb_id))

    query = '''
SELECT "Entry_ID" as entry_id, ed."Type" as type, dic.catgrpviewname as description, "Count"::integer as sets,
       0 as size from "Data_set" as ed
  LEFT JOIN dict.aditcatgrp as dic ON ed."Type" = dic.sfcategory
 WHERE ed."Entry_ID" like %s
UNION
SELECT bmrbid, 'time_domain_data', 'Time domain data', sets, size FROM web.timedomain_data where bmrbid like %s;'''
    cur.execute(query, [bmrb_id, bmrb_id])

    try:
        entry = next(get_valid_entries_from_redis(bmrb_id, r_conn=r_conn))[1]
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
                               'urls': [url % (bmrb_id, urlquote(x)) for x in saveframe_names]})

    return extra_data


def get_entry_id_tag(tag_or_category, database="macromolecules", cur=None):
    """ Returns the tag that contains the logical Entry ID. This isn't always the Entry_ID tag.

    You should always provide a Postgres cursor if you've already opened one."""

    if cur is None:
        cur = get_postgres_connection()[1]

    # Determine if this is a fully qualified tag or just the category
    try:
        tag_category = get_category_and_tag(tag_or_category)[0]
    except RequestError:
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
            raise ServerError("Unknown ID tag for tag: %s" % tag_or_category)

    cur.execute("""
SELECT tagfield
  FROM dict.val_item_tbl
  WHERE entryidflag='Y' AND lower(tagcategory)=lower(%s);""", [tag_category])

    try:
        return cur.fetchone()[0]
    except TypeError:
        raise RequestError("Invalid tag queried, unable to determine entryidflag.")


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
    saveframe, the identifier of the saveframe, and the name of the tag that
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
    # cur.execute('''SELECT val_item_tbl.originaltag,val_item_tbl.internalflag,
    # printflag,val_item_tbl.dictionaryseq,rowindexflg FROM dict.val_item_tbl,
    # dict.adit_item_tbl WHERE val_item_tbl.originaltag=
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
    cur.execute("""SELECT DISTINCT tagcategory FROM dict.val_item_tbl
                WHERE originalcategory=%(category)s AND loopflag<>'Y'""",
                {"category": category})
    table_name = cur.fetchone()[0]

    if configuration['debug']:
        print("Will look in table: %s" % table_name)

    # Get the sf_id for later
    cur.execute('''SELECT "Sf_ID","Sf_framecode" FROM %(table_name)s
                WHERE %(search_field)s=%(id)s ORDER BY "Sf_ID"''',
                {"id": entry_id, 'table_name': wrap_it_up(table_name),
                 "search_field": wrap_it_up(id_search_field)})

    # There is no matching saveframe found for their search term
    # and search field
    if cur.rowcount == 0:
        raise RequestError("No matching saveframe found.")
    sf_id, sf_framecode = cur.fetchone()

    # Create the NMR-STAR saveframe
    built_frame = pynmrstar.Saveframe.from_scratch(sf_framecode)
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


def create_combined_view():
    """ Create the combined schema from the other three schemas."""

    # Connect as the user that has write privileges
    conn, cur = get_postgres_connection(user="bmrb")

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
