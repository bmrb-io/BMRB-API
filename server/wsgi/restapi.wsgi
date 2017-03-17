#!/usr/bin/python

""" This code is used to provide the REST API interface. Under the hood
all of the work is done in utils/querymod.py - this just routes the queries
to the correct location and passes the results back."""

import os
import sys
import json
import logging
import traceback
from datetime import datetime
logging.basicConfig()

# Set up paths for imports and such
local_dir = os.path.dirname(__file__)
os.chdir(local_dir)
sys.path.append(local_dir)

# Import flask
from flask import Flask, request, Response
# Import the functions needed to service requests
from utils import querymod
# For catching exception
from utils.jsonrpc.exceptions import JSONRPCDispatchException as JSONRPCException

# Set up the flask application
application = Flask(__name__)

# Set up error handling
@application.errorhandler(JSONRPCException)
def handle_jsonrpc_error(error):
    """ Catches JSON-RPC exceptions (ones we raise) and formats
    them for the REST interface."""

    # Assume the client did something wrong with the 400 error
    return return_json({"error":error.error.message}, code=400)

@application.errorhandler(Exception)
def handle_other_errors(error):
    """ Catches any other exceptions and formats them for REST. Only
    displays the actual error to local clients (to prevent disclosing
    issues that could be security vulnerabilities)."""

    if querymod.check_local_ip(request.remote_addr):
        return Response(traceback.format_exc(), mimetype="text/plain")
    else:
        msg = "Server error. Contact webmaster@bmrb.wisc.edu."
        return return_json({"error": msg}, code=500)

def return_json(obj, encode=True, code=None):
    """ Returns a flask Response object containing the JSON-encoded version of
    the passed object. If encode is set to False than a Response with the string
    version of the object is returned."""

    # JSON encode if necessary
    if encode:
        obj = json.dumps(obj)

    response = Response(response=obj, mimetype="application/json")

    # Set an error code
    if "error" in obj:
        # Assume the user made the mistake
        response.status_code = 400

    # If a specific error code was provided send it rather than the default
    if code:
        response.status_code = code

    return response

@application.route('/')
def no_params():
    """ Return an error if they have not specified which method type to use."""
    return "No method specified!"

@application.route('/list_entries/')
@application.route('/list_entries/<entry_type>')
def list_entries(entry_type="combined"):
    """ Return a list of all valid BMRB entries."""

    entries = querymod.list_entries(database=entry_type)
    return return_json(entries)

@application.route('/debug', methods=('GET', 'POST'))
def debug():
    """ This method prints some debugging information."""
    debug_str = "Secure: " + str(request.is_secure)
    debug_str += "<br>URL: " + str(request.url)
    debug_str += "<br>Method: " + str(request.method)
    debug_str += "<br>Viewing from: " + str(request.remote_addr)
    debug_str += "<br>Avail: %s" % dir(request)

    red = querymod.get_redis_connection()

    for key in ['metabolomics', 'macromolecules', 'chemcomps', 'combined']:
        update_string = red.hget("%s:meta" % key, 'update_time')
        if update_string:
            update_time = datetime.fromtimestamp(float(update_string))
            update_string = update_time.strftime('%Y-%m-%d %H:%M:%S')
        debug_str += "<br>Last %s DB update: %s" % (key, update_string)

    return debug_str

@application.route('/chemical_shifts/')
@application.route('/chemical_shifts/<atom_id>')
@application.route('/chemical_shifts/<atom_id>/<database>')
def chemical_shifts(atom_id=None, database="macromolecules"):
    """ Return a list of all chemical shifts that match the selectors"""

    # To enable changing URL syntax in the future to remove /<atom_id>/
    if request.args.get('atom_id', None):
        atom_id = request.args.get('atom_id', None)

    return return_json(querymod.chemical_shift_search_1d(shift_val=request.args.get('shift', None),
                                                         threshold=request.args.get('threshold', .03),
                                                         atom_type=request.args.get('atom_type', None),
                                                         atom_id=atom_id,
                                                         comp_id=request.args.get('comp_id', None),
                                                         database=database))

@application.route('/entry/', methods=('POST', 'GET'))
@application.route('/entry/<entry_id>/')
@application.route('/entry/<entry_id>/<format_>/')
def get_entry(entry_id=None, format_="json"):
    """ Returns an entry in the specified format."""

    # If they are storing
    if request.method == "POST":
        return return_json(querymod.store_uploaded_entry(data=request.data))

    # Loading
    else:
        if entry_id is None:
            # They are trying to send an entry using GET
            if request.args.get('data', None):
                return return_json({"error":"Cannot access this page through GET."})
            # They didn't specify an entry ID
            else:
                return return_json({"error":"You must specify the entry number."})

        # Get the entry
        entry = querymod.get_entries(ids=entry_id, format=format_)

        # Make sure it is a valid entry
        if not entry_id in entry:
            return return_json({"error": "Entry '%s' does not exist in the "
                                        "public database." % entry_id},
                               code=404)

        # Bypass JSON encode/decode cycle
        if format_ == "json":
            return return_json("""{"%s": %s}""" % (entry_id, entry[entry_id]),
                               encode=False)

        # Special case to return raw nmrstar
        elif format_ == "rawnmrstar":
            return Response(entry[entry_id], mimetype="text/nmrstar")

        # Special case for raw zlib
        elif format_ == "zlib":
            return Response(entry[entry_id], mimetype="application/zlib")

        # Return the entry in any other format
        return return_json(entry)

@application.route('/saveframe/<entry_id>/<saveframe_category>')
@application.route('/saveframe/<entry_id>/<saveframe_category>/<format_>/')
def get_saveframe(entry_id, saveframe_category, format_="json"):
    """ Returns a saveframe in the specified format."""
    result = querymod.get_saveframes(ids=entry_id, keys=saveframe_category,
                                     format=format_)
    return return_json(result)

@application.route('/loop/<entry_id>/<loop_category>')
@application.route('/loop/<entry_id>/<loop_category>/<format_>/')
def get_loop(entry_id, loop_category, format_="json"):
    """ Returns a loop in in the specified format."""
    return return_json(querymod.get_loops(ids=entry_id, keys=loop_category,
                                          format=format_))

@application.route('/tag/<entry_id>/<tag_name>')
def get_tag(entry_id, tag_name):
    """ Returns all values for the tag for the given entry."""
    return return_json(querymod.get_tags(ids=entry_id, keys=tag_name))

@application.route('/get_id_from_search/<tag_name>/<tag_value>')
@application.route('/get_id_from_search/<tag_name>/<tag_value>/<schema>')
def get_id_from_search(tag_name, tag_value, schema="macromolecules"):
    """ Returns all BMRB IDs that were found when querying for entries
    which contain the supplied value for the supplied tag. """

    sp = tag_name.split(".")
    if sp[0].startswith("_"):
        sp[0] = sp[0][1:]
    if len(sp) < 2:
        return return_json({"error": "You must provide a full tag name with saveframe included. For example: Entry.Experimental_method_subtype"})

    # We don't know if this is an "ID" or "Entry_ID" saveframe...
    try:
        result = querymod.select(['Entry_ID'], sp[0], where_dict={sp[1]:tag_value},
                                 modifiers=['lower'], schema=schema)
    except JSONRPCException:
        try:
            result = querymod.select(['ID'], sp[0], where_dict={sp[1]:tag_value},
                                     modifiers=['lower'], schema=schema)
        except JSONRPCException:
            return return_json({"error": "Either the saveframe or the tag was not found: %s" % tag_name})

    return return_json(result[result.keys()[0]])

@application.route('/enumerations/<tag_name>')
def get_enumerations(tag_name):
    """ Returns all enumerations for a given tag."""

    return return_json(querymod.get_enumerations(tag=tag_name,
                                                 term=request.args.get('term')))

@application.route('/select', methods=('GET', 'POST'))
@application.route('/select')
def select():
    """ Performs an advanced select query. """

    # Check for GET request
    if request.method == "GET":
        return return_json({"error":"Cannot access this page through GET."})

    data = json.loads(request.get_data(cache=False, as_text=True))

    return return_json(querymod.process_select(**data))

# Software queries
@application.route('/software/entry/<entry_id>/')
def get_software_by_entry(entry_id):
    """ Returns the software used on a per-entry basis. """
    return return_json(querymod.get_entry_software(entry_id))

@application.route('/software/package/<package_name>')
@application.route('/software/package/<package_name>/<database>')
def get_software_by_package(package_name, database="macromolcule"):
    """ Returns the entries that used a particular software package. Search
    is done case-insensitive and is an x in y search rather than x == y
    search. """
    return return_json(querymod.get_software_entries(package_name, database=database))

@application.route('/software/name_suggestions')
@application.route('/software/name_suggestions/<database>')
def get_software_suggestions(database="macromolecules"):
    """ Returns new software name suggestions. """

    return Response(querymod.suggest_new_software_links(database=database), mimetype="text/csv")

@application.route('/instant/')
def get_instant():
    """ Do the instant search. """

    return return_json(querymod.get_instant_search(term=request.args.get('term')))

@application.route('/software/')
def get_software_summary():
    """ Returns a summary of all software used in all entries. """

    return return_json(querymod.get_software_summary())

@application.route('/status')
def get_status():
    """ Returns the server status."""
    return return_json(querymod.get_status())

# Queries that run commands

@application.route('/validate/<entry_id>')
def validate_entry(entry_id):
    """ Returns the validation report for the given entry. """

    return return_json(querymod.get_chemical_shift_validation(ids=entry_id))
