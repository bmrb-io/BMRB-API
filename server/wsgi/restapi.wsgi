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

    return return_json({"error":error.error.message})

@application.errorhandler(Exception)
def handle_other_errors(error):
    """ Catches any other exceptions and formats them for REST. Only
    displays the actual error to local clients (to prevent disclosing
    issues that could be security vulnerabilities)."""

    if querymod.check_local_ip(request.remote_addr):
        return Response(traceback.format_exc(), mimetype="text/plain")
    else:
        msg = "Server error. Contact webmaster@bmrb.wisc.edu."
        return return_json({"error": msg})

def return_json(obj, encode=True):
    """ Returns a flask Response object containing the JSON-encoded version of
    the passed object. If encode is set to False than a Response with the string
    version of the object is returned."""

    if encode:
        return Response(response=json.dumps(obj), mimetype="application/json")
    else:
        return Response(response=obj, mimetype="application/json")

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
@application.route('/chemical_shifts/<atom_type>')
@application.route('/chemical_shifts/<atom_type>/<database>')
def chemical_shifts(atom_type=None, database=None):
    """ Return a list of all chemical shifts for the given atom type."""
    return return_json(querymod.get_chemical_shifts(atom_type=atom_type,
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
            return return_json({"error":"Cannot access this page through GET."})
        if format_ == "json":
            # You could just use the portion in the "else" below, but this
            #  is faster because the entry doesn't have to be JSON decoded and
            #   then JSON encoded.
            return return_json(querymod.get_raw_entry(entry_id), encode=False)
        else:
            # Special case to return raw nmrstar
            if format_ == "rawnmrstar":
                ent = querymod.get_entries(ids=entry_id, format="nmrstar")[entry_id]
                return Response(str(ent), mimetype="text/nmrstar")

            # Return the entry in any other format
            result = querymod.get_entries(ids=entry_id, format=format_)
            return return_json(result)

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
        result = querymod.select(['ID'], sp[0], where_dict={sp[1]:tag_value},
                       modifiers=['lower'], schema=schema)
    except JSONRPCException:
        try:
            result = querymod.select(['Entry_ID'], sp[0], where_dict={sp[1]:tag_value},
                       modifiers=['lower'], schema=schema)
        except JSONRPCException:
            return return_json({"error": "Either the saveframe or the tag was not found: %s" % tag_name})

    return return_json(result[result.keys()[0]])

@application.route('/enumerations/<tag_name>')
def get_enumerations(tag_name):
    """ Returns all enumerations for a given tag."""

    return return_json(querymod.get_enumerations(tag=tag_name,
                                                 term=request.args.get('term')))

@application.route('/status')
def get_status():
    """ Returns the server status."""
    return return_json(querymod.get_status())

# Queries that run commands

@application.route('/validate/<entry_id>')
def validate_entry(entry_id):
    """ Returns the validation report for the given entry. """

    return return_json(querymod.get_chemical_shift_validation(ids=entry_id))
