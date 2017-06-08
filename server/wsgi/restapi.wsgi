#!/usr/bin/python

""" This code is used to provide the REST API interface. Under the hood
all of the work is done in utils/querymod.py - this just routes the queries
to the correct location and passes the results back."""

import os
import sys
import time
import traceback
from datetime import datetime
import logging
from logging.handlers import RotatingFileHandler, SMTPHandler
from pythonjsonlogger import jsonlogger
try:
    import simplejson as json
except ImportError:
    import json

# Set up paths for imports and such
local_dir = os.path.dirname(__file__)
os.chdir(local_dir)
sys.path.append(local_dir)

# Import flask
from flask import Flask, request, Response, jsonify
# Import the functions needed to service requests
from utils import querymod

# Set up the flask application
application = Flask(__name__)

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
if not querymod.configuration['debug']:

    if (querymod.configuration.get('smtp')
            and querymod.configuration['smtp'].get('server')
            and querymod.configuration['smtp'].get('admins')):

        mail_handler = SMTPHandler(mailhost=querymod.configuration['smtp']['server'],
                                   fromaddr='apierror@webapi.bmrb.wisc.edu',
                                   toaddrs=querymod.configuration['smtp']['admins'],
                                   subject='BMRB API Error occured')
        mail_handler.setLevel(logging.WARNING)
        application.logger.addHandler(mail_handler)
    else:
        logging.warning("Could not set up SMTP logger because the configuration"
                        " was not specified.")

# Set up error handling
@application.errorhandler(querymod.ServerError)
@application.errorhandler(querymod.RequestError)
def handle_our_errors(error):
    """ Handles exceptions we raised ourselves. """

    application.logger.warning("Handled error raised in %s: %s", request.url, error.message)

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
                 request.headers.get('User-Agent','?').split()[0],
                 request.headers.get('Application', 'unknown'))

    jlogger.info({"user-agent": request.headers.get('User-Agent'),
                  "method": request.method, "endpoint": request.endpoint,
                  "application": request.headers.get('Application'),
                  "path": request.full_path, "ip": request.remote_addr,
                  "local": check_local_ip(), "time": time.time()})

    # Don't pretty-print JSON unless local user and in debug mode
    if check_local_ip() and querymod.configuration['debug']:
        application.config['JSONIFY_PRETTYPRINT_REGULAR'] = True
    else:
        application.config['JSONIFY_PRETTYPRINT_REGULAR'] = False

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
        return jsonify(querymod.store_uploaded_entry(data=request.data))

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
        args = sum([1 if request.args.get('saveframe', None) else 0,
                    1 if request.args.get('loop', None) else 0,
                    1 if request.args.get('tag', None) else 0])
        if args > 1:
            raise querymod.RequestError("Request either loop(s), saveframe(s), "
                                        "or tag(s) but not more than one "
                                        "simultaneously.")

        # See if they are requesting one or more saveframe
        elif request.args.get('saveframe', None):
            result = querymod.get_saveframes(ids=entry_id,
                                             keys=request.args.getlist('saveframe'),
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

@application.route('/search')
@application.route('/search/')
def print_search_options():
    """ Returns a list of the search methods."""

    result = ""
    for method in ["get_all_values_for_tag", "get_id_by_tag_value",
                   "chemical_shifts"]:
        result += '<a href="%s">%s</a><br>' % (method, method)

    return result

@application.route('/search/multiple_shift_search')
def multiple_shift_search():
    """ Finds entries that match at least some of the peaks. """

    peaks = request.args.getlist('shift', None)
    if not peaks:
        raise querymod.RequestError("You must specify at least one shift to search for.")

    return jsonify(querymod.multiple_peak_search(peaks,
                                                 database=get_db("metabolomics")))

@application.route('/search/chemical_shifts')
def get_chemical_shifts():
    """ Return a list of all chemical shifts that match the selectors"""

    #if request.is_json:
        #return jsonify(request.get_json())

    return jsonify(querymod.chemical_shift_search_1d(shift_val=request.args.getlist('shift', None),
                                                     threshold=request.args.get('threshold', .03),
                                                     atom_type=request.args.get('atom_type', None),
                                                     atom_id=request.args.getlist('atom_id', None),
                                                     comp_id=request.args.getlist('comp_id', None),
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
@application.route('/search/get_id_by_tag_value/<tag_name>/<tag_value>')
def get_id_from_search(tag_name=None, tag_value=None):
    """ Returns all BMRB IDs that were found when querying for entries
    which contain the supplied value for the supplied tag. """

    database = get_db('macromolecules')

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

    result = querymod.select(['Entry_ID'], sp[0], where_dict={sp[1]:tag_value},
                             modifiers=['lower'], database=database)

    return jsonify(result[result.keys()[0]])

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
@application.route('/software/entry/')
@application.route('/software/entry/<entry_id>/')
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

    return jsonify(status)

# Queries that run commands
@application.route('/validate/')
@application.route('/validate/<entry_id>')
def validate_entry(entry_id=None):
    """ Returns the validation report for the given entry. """

    if not entry_id:
        raise querymod.RequestError("You must specify the entry ID.")

    return jsonify(querymod.get_chemical_shift_validation(ids=entry_id))


# Helper methods
def get_db(default="macromolecules",
           valid_list=["metabolomics", "macromolecules", "combined"]):
    """ Make sure the DB specified is valid. """

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
