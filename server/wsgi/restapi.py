#!/usr/bin/python

""" This code is used to provide the REST API interface. Under the hood
all of the work is done in utils/querymod.py - this just routes the queries
to the correct location and passes the results back."""

from __future__ import print_function

import os
import sys
import time
import datetime
import traceback
import logging
from logging.handlers import RotatingFileHandler, SMTPHandler
from uuid import uuid4

import requests
from itsdangerous import URLSafeSerializer, BadSignature
from pythonjsonlogger import jsonlogger
from validate_email import validate_email

try:
    import simplejson as json
except ImportError:
    import json

# Import flask
from flask import Flask, request, Response, jsonify, url_for, redirect, send_file
from werkzeug.utils import secure_filename
from flask_mail import Mail, Message

# Set up paths for imports and such
local_dir = os.path.dirname(__file__)
os.chdir(local_dir)
sys.path.append(local_dir)

# Import the functions needed to service requests - must be after path updates
from utils import querymod
pynmrstar = querymod.pynmrstar
from utils import depositions

# Set up the flask application
application = Flask(__name__)
application.url_map.strict_slashes = False

# Set debug if running from command line
if application.debug:
    from flask_cors import CORS

    querymod.configuration['debug'] = True
    CORS(application)

application.secret_key = querymod.configuration['secret_key']

# Set up the logging

# First figure out where to log
request_log_file = os.path.join(local_dir, "logs", "requests.log")
application_log_file = os.path.join(local_dir, "logs", "application.log")
request_json_file = os.path.join(local_dir, "logs", "json_requests.log")
if querymod.configuration.get('log'):
    if querymod.configuration['log'].get('json'):
        request_json_file = querymod.configuration['log']['json']
    if querymod.configuration['log'].get('request'):
        request_log_file = querymod.configuration['log']['request']
    if querymod.configuration['log'].get('application'):
        application_log_file = querymod.configuration['log']['application']

# Set up the standard logger
app_formatter = logging.Formatter('[%(asctime)s]:%(levelname)s:%(funcName)s: %(message)s')
application_log = RotatingFileHandler(application_log_file, maxBytes=1048576, backupCount=100)
application_log.setFormatter(app_formatter)
application.logger.addHandler(application_log)
application.logger.setLevel(logging.WARNING)

# Set up the request loggers

# Plain text logger
request_formatter = logging.Formatter('[%(asctime)s]: %(message)s')
request_log = RotatingFileHandler(request_log_file, maxBytes=1048576, backupCount=100)
request_log.setFormatter(request_formatter)
rlogger = logging.getLogger("rlogger")
rlogger.setLevel(logging.INFO)
rlogger.addHandler(request_log)
rlogger.propagate = False

# JSON logger
json_formatter = jsonlogger.JsonFormatter()
application_json = RotatingFileHandler(request_json_file, maxBytes=1048576, backupCount=100)
application_json.setFormatter(json_formatter)
jlogger = logging.getLogger("jlogger")
jlogger.setLevel(logging.INFO)
jlogger.addHandler(application_json)
jlogger.propagate = False

# Set up the SMTP handler
if (querymod.configuration.get('smtp')
        and querymod.configuration['smtp'].get('server')
        and querymod.configuration['smtp'].get('admins')):

    # Don't send error e-mails in debugging mode
    if not querymod.configuration['debug']:
        mail_handler = SMTPHandler(mailhost=querymod.configuration['smtp']['server'],
                                   fromaddr='apierror@webapi.bmrb.wisc.edu',
                                   toaddrs=querymod.configuration['smtp']['admins'],
                                   subject='BMRB API Error occurred')
        mail_handler.setLevel(logging.WARNING)
        application.logger.addHandler(mail_handler)

    # Set up the mail interface
    application.config.update(
        MAIL_SERVER=querymod.configuration['smtp']['server'],
        # TODO: Make this configurable
        MAIL_DEFAULT_SENDER='noreply@bmrb.wisc.edu'
    )
    mail = Mail(application)
else:
    logging.warning("Could not set up SMTP logger because the configuration"
                    " was not specified.")


# Set up error handling
@application.errorhandler(querymod.ServerError)
@application.errorhandler(querymod.RequestError)
def handle_our_errors(error):
    """ Handles exceptions we raised ourselves. """

    application.logger.info("Handled error raised in %s: %s", request.url, error.message)

    response = jsonify(error.to_dict())
    response.status_code = error.status_code
    return response


@application.errorhandler(Exception)
def handle_other_errors(error):
    """ Catches any other exceptions and formats them. Only
    displays the actual error to local clients (to prevent disclosing
    issues that could be security vulnerabilities)."""

    application.logger.critical("Unhandled exception raised on request %s %s"
                                "\n\nValues: %s\n\n%s",
                                request.method, request.url,
                                request.values,
                                traceback.format_exc())

    if check_local_ip():
        return Response("NOTE: You are seeing this error because your IP was "
                        "recognized as a local IP:\n%s" %
                        traceback.format_exc(), mimetype="text/plain")
    else:
        response = jsonify({"error": "Server error. Contact webmaster@bmrb.wisc.edu."})
        response.status_code = 500
        return response


# Set up logging
@application.before_request
def log_request():
    """ Log all requests. """
    rlogger.info("%s %s %s %s %s", request.remote_addr, request.method,
                 request.full_path,
                 request.headers.get('User-Agent', '?').split()[0],
                 request.headers.get('Application', 'unknown'))

    jlogger.info({"user-agent": request.headers.get('User-Agent'),
                  "method": request.method, "endpoint": request.endpoint,
                  "application": request.headers.get('Application'),
                  "path": request.full_path, "ip": request.remote_addr,
                  "local": check_local_ip(), "time": time.time()})

    # Don't pretty-print JSON unless local user and in debug mode
    application.config['JSONIFY_PRETTYPRINT_REGULAR'] = (check_local_ip() and
                                                         querymod.configuration['debug']) or request.args.get(
        "prettyprint") == "true"


@application.route('/favicon.ico')
def favicon():
    """ Return the favicon. """

    return redirect(url_for('static', filename='favicon.ico'))


@application.route('/')
def no_params():
    """ Return an error if they have not specified which method type to use."""

    result = ""
    for method in querymod._METHODS:
        result += '<a href="%s">%s</a><br>' % (method, method)

    return result


@application.route('/list_entries')
def list_entries():
    """ Return a list of all valid BMRB entries."""

    entries = querymod.list_entries(database=get_db("combined",
                                                    valid_list=['metabolomics',
                                                                'macromolecules',
                                                                'chemcomps',
                                                                'combined']))
    return jsonify(entries)


@application.route('/entry/', methods=('POST', 'GET'))
@application.route('/entry/<entry_id>')
def get_entry(entry_id=None):
    """ Returns an entry in the specified format."""

    # Get the format they want the results in
    format_ = request.args.get('format', "json")

    # If they are storing
    if request.method == "POST":
        return jsonify(querymod.store_uploaded_entry(request))

    # Loading
    else:
        if entry_id is None:
            # They are trying to send an entry using GET
            if request.args.get('data', None):
                raise querymod.RequestError("Cannot access this page through GET.")
            # They didn't specify an entry ID
            else:
                raise querymod.RequestError("You must specify the entry ID.")

        # Make sure it is a valid entry
        if not querymod.check_valid(entry_id):
            raise querymod.RequestError("Entry '%s' does not exist in the "
                                        "public database." % entry_id,
                                        status_code=404)

        # See if they specified more than one of [saveframe, loop, tag]
        args = sum([1 if request.args.get('saveframe_category', None) else 0,
                    1 if request.args.get('saveframe_name', None) else 0,
                    1 if request.args.get('loop', None) else 0,
                    1 if request.args.get('tag', None) else 0])
        if args > 1:
            raise querymod.RequestError("Request either loop(s), saveframe(s) by"
                                        " category, saveframe(s) by name, "
                                        "or tag(s) but not more than one "
                                        "simultaneously.")

        # See if they are requesting one or more saveframe
        elif request.args.get('saveframe_category', None):
            result = querymod.get_saveframes_by_category(ids=entry_id,
                                                         keys=request.args.getlist('saveframe_category'),
                                                         format=format_)
            return jsonify(result)

        # See if they are requesting one or more saveframe
        elif request.args.get('saveframe_name', None):
            result = querymod.get_saveframes_by_name(ids=entry_id,
                                                     keys=request.args.getlist('saveframe_name'),
                                                     format=format_)
            return jsonify(result)

        # See if they are requesting one or more loop
        elif request.args.get('loop', None):
            return jsonify(querymod.get_loops(ids=entry_id,
                                              keys=request.args.getlist('loop'),
                                              format=format_))

        # See if they want a tag
        elif request.args.get('tag', None):
            return jsonify(querymod.get_tags(ids=entry_id,
                                             keys=request.args.getlist('tag')))

        # They want an entry
        else:
            # Get the entry
            entry = querymod.get_entries(ids=entry_id, format=format_)

            # Bypass JSON encode/decode cycle
            if format_ == "json":
                return Response("""{"%s": %s}""" % (entry_id, entry[entry_id]),
                                mimetype="application/json")

            # Special case to return raw nmrstar
            elif format_ == "rawnmrstar":
                return Response(entry[entry_id], mimetype="text/nmrstar")

            # Special case for raw zlib
            elif format_ == "zlib":
                return Response(entry[entry_id], mimetype="application/zlib")

            # Return the entry in any other format
            return jsonify(entry)


@application.route('/schema')
@application.route('/schema/<schema_version>')
def return_schema(schema_version=None):
    """ Returns the BMRB schema as JSON. """
    return jsonify(querymod.get_schema(schema_version))


@application.route('/molprobity/')
@application.route('/molprobity/<pdb_id>')
@application.route('/molprobity/<pdb_id>/oneline')
def return_molprobity_oneline(pdb_id=None):
    """Returns the molprobity data for a PDB ID. """

    if not pdb_id:
        raise querymod.RequestError("You must specify the PDB ID.")

    return jsonify(querymod.get_molprobity_data(pdb_id))


@application.route('/molprobity/<pdb_id>/residue')
def return_molprobity_residue(pdb_id):
    """Returns the molprobity residue data for a PDB ID. """

    return jsonify(querymod.get_molprobity_data(pdb_id,
                                                residues=request.args.getlist('r')))


@application.route('/search')
@application.route('/search/')
def print_search_options():
    """ Returns a list of the search methods."""

    result = ""
    for method in ["chemical_shifts", "fasta", "get_all_values_for_tag",
                   "get_bmrb_data_from_pdb_id",
                   "get_id_by_tag_value", "get_bmrb_ids_from_pdb_id",
                   "get_pdb_ids_from_bmrb_id", "multiple_shift_search"]:
        result += '<a href="%s">%s</a><br>' % (method, method)

    return result


@application.route('/search/get_bmrb_data_from_pdb_id/')
@application.route('/search/get_bmrb_data_from_pdb_id/<pdb_id>')
def get_bmrb_data_from_pdb_id(pdb_id=None):
    """ Returns the associated BMRB data for a PDB ID. """

    if not pdb_id:
        raise querymod.RequestError("You must specify a PDB ID.")

    result = []
    for item in querymod.get_bmrb_ids_from_pdb_id(pdb_id):
        data = querymod.get_extra_data_available(item['bmrb_id'])
        if data:
            result.append({'bmrb_id': item['bmrb_id'], 'match_types': item['match_types'],
                           'url': 'http://www.bmrb.wisc.edu/data_library/summary/index.php?bmrbId=%s' % item['bmrb_id'],
                           'data': data})

    return jsonify(result)


@application.route('/search/multiple_shift_search')
def multiple_shift_search():
    """ Finds entries that match at least some of the peaks. """

    peaks = request.args.getlist('shift')
    if not peaks:
        peaks = request.args.getlist('s')
    else:
        peaks.extend(list(request.args.getlist('s')))

    if not peaks:
        raise querymod.RequestError("You must specify at least one shift to search for.")

    return jsonify(querymod.multiple_peak_search(peaks,
                                                 database=get_db("metabolomics")))


@application.route('/search/chemical_shifts')
def get_chemical_shifts():
    """ Return a list of all chemical shifts that match the selectors"""

    cs1d = querymod.chemical_shift_search_1d
    return jsonify(cs1d(shift_val=request.args.getlist('shift'),
                        threshold=request.args.get('threshold', .03),
                        atom_type=request.args.get('atom_type', None),
                        atom_id=request.args.getlist('atom_id'),
                        comp_id=request.args.getlist('comp_id'),
                        conditions=request.args.get('conditions', False),
                        database=get_db("macromolecules")))


@application.route('/search/get_all_values_for_tag/')
@application.route('/search/get_all_values_for_tag/<tag_name>')
def get_all_values_for_tag(tag_name=None):
    """ Returns all entry numbers and corresponding tag values."""

    result = querymod.get_all_values_for_tag(tag_name, get_db('macromolecules'))
    return jsonify(result)


@application.route('/search/get_id_by_tag_value/')
@application.route('/search/get_id_by_tag_value/<tag_name>/')
@application.route('/search/get_id_by_tag_value/<tag_name>/<path:tag_value>')
def get_id_from_search(tag_name=None, tag_value=None):
    """ Returns all BMRB IDs that were found when querying for entries
    which contain the supplied value for the supplied tag. """

    database = get_db('macromolecules',
                      valid_list=['metabolomics', 'macromolecules', 'chemcomps'])

    if not tag_name:
        raise querymod.RequestError("You must specify the tag name.")
    if not tag_value:
        raise querymod.RequestError("You must specify the tag value.")

    sp = tag_name.split(".")
    if sp[0].startswith("_"):
        sp[0] = sp[0][1:]
    if len(sp) < 2:
        raise querymod.RequestError("You must provide a full tag name with "
                                    "saveframe included. For example: "
                                    "Entry.Experimental_method_subtype")

    id_field = querymod.get_entry_id_tag(tag_name, database)
    result = querymod.select([id_field], sp[0], where_dict={sp[1]: tag_value},
                             modifiers=['lower'], database=database)
    return jsonify(result[result.keys()[0]])


@application.route('/search/get_bmrb_ids_from_pdb_id/')
@application.route('/search/get_bmrb_ids_from_pdb_id/<pdb_id>')
def get_bmrb_ids_from_pdb_id(pdb_id=None):
    """ Returns the associated BMRB IDs for a PDB ID. """

    if not pdb_id:
        raise querymod.RequestError("You must specify a PDB ID.")

    result = querymod.get_bmrb_ids_from_pdb_id(pdb_id)
    return jsonify(result)


@application.route('/search/get_pdb_ids_from_bmrb_id/')
@application.route('/search/get_pdb_ids_from_bmrb_id/<pdb_id>')
def get_pdb_ids_from_bmrb_id(pdb_id=None):
    """ Returns the associated BMRB IDs for a PDB ID. """

    if not pdb_id:
        raise querymod.RequestError("You must specify a BMRB ID.")

    result = querymod.get_pdb_ids_from_bmrb_id(pdb_id)
    return jsonify(result)


@application.route('/search/fasta/')
@application.route('/search/fasta/<query>')
def fasta_search(query=None):
    """Performs a FASTA search on the specified query in the BMRB database."""

    if not query:
        raise querymod.RequestError("You must specify a sequence.")

    return jsonify(querymod.fasta_search(query,
                                         a_type=request.args.get('type', 'polymer'),
                                         e_val=request.args.get('e_val')))


@application.route('/enumerations/')
@application.route('/enumerations/<tag_name>')
def get_enumerations(tag_name=None):
    """ Returns all enumerations for a given tag."""

    if not tag_name:
        raise querymod.RequestError("You must specify the tag name.")

    return jsonify(querymod.get_enumerations(tag=tag_name,
                                             term=request.args.get('term')))


@application.route('/select', methods=('GET', 'POST'))
def select():
    """ Performs an advanced select query. """

    # Check for GET request
    if request.method == "GET":
        raise querymod.RequestError("Cannot access this page through GET.")

    data = json.loads(request.get_data(cache=False, as_text=True))

    return jsonify(querymod.process_select(**data))


@application.route('/software/')
def get_software_summary():
    """ Returns a summary of all software used in all entries. """

    return jsonify(querymod.get_software_summary())


# Software queries
@application.route('/entry/<entry_id>/software')
def get_software_by_entry(entry_id=None):
    """ Returns the software used on a per-entry basis. """

    if not entry_id:
        raise querymod.RequestError("You must specify the entry ID.")

    return jsonify(querymod.get_entry_software(entry_id))


@application.route('/software/package/')
@application.route('/software/package/<package_name>')
def get_software_by_package(package_name=None):
    """ Returns the entries that used a particular software package. Search
    is done case-insensitive and is an x in y search rather than x == y
    search. """

    if not package_name:
        raise querymod.RequestError("You must specify the software package name.")

    return jsonify(querymod.get_software_entries(package_name,
                                                 database=get_db('macromolecules')))


@application.route('/entry/<entry_id>/experiments')
def get_metabolomics_data(entry_id):
    """ Return the experiments available for an entry. """

    return jsonify(querymod.get_experiments(entry=entry_id))


@application.route('/entry/<entry_id>/citation')
def get_citation(entry_id):
    """ Return the citation information for an entry in the requested format. """

    format_ = request.args.get('format', "python")
    if format_ == "json-ld":
        format_ = "python"

    # Get the citation
    citation = querymod.get_citation(entry_id, format_=format_)

    # Bibtex
    if format_ == "bibtex":
        return Response(citation, mimetype="application/x-bibtex",
                        headers={"Content-disposition": "attachment; filename=%s.bib" % entry_id})
    elif format_ == "text":
        return Response(citation, mimetype="text/plain")
    # JSON+LD
    else:
        return jsonify(citation)


@application.route('/instant')
def get_instant():
    """ Do the instant search. """

    if not request.args.get('term', None):
        raise querymod.RequestError("You must specify the search term using ?term=search_term")

    return jsonify(querymod.get_instant_search(term=request.args.get('term'),
                                               database=get_db('combined')))


@application.route('/status')
def get_status():
    """ Returns the server status."""

    status = querymod.get_status()

    if check_local_ip():
        # Raise an exception to test SMTP error notifications working
        if request.args.get("exception"):
            raise Exception("Unhandled exception test.")

        status['URL'] = request.url
        status['secure'] = request.is_secure
        status['remote_address'] = request.remote_addr
        status['debug'] = querymod.configuration.get('debug')

    return jsonify(status)


# Queries that run commands
@application.route('/entry/<entry_id>/validate')
def validate_entry(entry_id=None):
    """ Returns the validation report for the given entry. """

    if not entry_id:
        raise querymod.RequestError("You must specify the entry ID.")

    return jsonify(querymod.get_chemical_shift_validation(ids=entry_id))


# Helper methods
def get_db(default="macromolecules",
           valid_list=None):
    """ Make sure the DB specified is valid. """

    if not valid_list:
        valid_list = ["metabolomics", "macromolecules", "combined", "chemcomps"]

    database = request.args.get('database', default)

    if database not in valid_list:
        raise querymod.RequestError("Invalid database: %s." % database)

    return database


def check_local_ip():
    """ Checks if the given IP is a local user."""

    for local_address in querymod.configuration['local-ips']:
        if request.remote_addr.startswith(local_address):
            return True

    return False
