#!/usr/bin/python

""" This code is used to provide the REST API interface. Under the hood
all of the work is done in utils/querymod.py - this just routes the queries
to the correct location and passes the results back."""

import os
import sys
import logging
import traceback
from datetime import datetime
logging.basicConfig()

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

# Don't pretty-print JSON unless in debug mode
if not querymod.configuration['debug']:
    application.config['JSONIFY_PRETTYPRINT_REGULAR'] = False

# Set up error handling
@application.errorhandler(querymod.ServerError)
@application.errorhandler(querymod.RequestError)
def handle_our_errors(error):
    """ Handles exceptions we raised ourselves. """

    response = jsonify(error.to_dict())
    response.status_code = error.status_code
    return response

@application.errorhandler(Exception)
def handle_other_errors(error):
    """ Catches any other exceptions and formats thme. Only
    displays the actual error to local clients (to prevent disclosing
    issues that could be security vulnerabilities)."""

    if querymod.check_local_ip(request.remote_addr):
        return Response("NOTE: You are seeing this error because your IP was "
                        "recognized as a local IP:\n%s" %
                        traceback.format_exc(), mimetype="text/plain")
    else:
        response = jsonify({"error": "Server error. Contact webmaster@bmrb.wisc.edu."})
        response.status_code = 500
        return response

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

    entries = querymod.list_entries(database=request.args.get('database', "combined"))
    return jsonify(entries)

@application.route('/debug', methods=('GET', 'POST'))
def debug():
    """ This method prints some debugging information."""

    result = {}
    result['secure'] = request.is_secure
    result['URL'] = request.url
    result['method'] = request.method
    result['remote_address'] = request.remote_addr

    red = querymod.get_redis_connection()

    for key in ['metabolomics', 'macromolecules', 'chemcomps', 'combined']:
        update_string = red.hget("%s:meta" % key, 'update_time')
        if update_string:
            update_time = datetime.fromtimestamp(float(update_string))
            update_string = update_time.strftime('%Y-%m-%d %H:%M:%S')
        result[key] = {'update':update_string}

    return jsonify(result)

@application.route('/chemical_shifts')
def chemical_shifts():
    """ Return a list of all chemical shifts that match the selectors"""

    return jsonify(querymod.chemical_shift_search_1d(shift_val=request.args.get('shift', None),
                                                     threshold=request.args.get('threshold', .03),
                                                     atom_type=request.args.get('atom_type', None),
                                                     atom_id=request.args.get('atom_id', None),
                                                     comp_id=request.args.get('comp_id', None),
                                                     database=request.args.get('database', None)))


@application.route('/entry', methods=('POST', 'GET'))
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


@application.route('/get_id_from_search/')
@application.route('/get_id_from_search/<tag_name>/')
@application.route('/get_id_from_search/<tag_name>/<tag_value>')
@application.route('/get_id_from_search/<tag_name>/<tag_value>/<schema>')
def get_id_from_search(tag_name=None, tag_value=None, schema="macromolecules"):
    """ Returns all BMRB IDs that were found when querying for entries
    which contain the supplied value for the supplied tag. """

    if not tag_name:
        raise querymod.RequestError("You must specify the tag name.")
    if not tag_value:
        raise querymod.RequestError("You must specify the tag value.")

    sp = tag_name.split(".")
    if sp[0].startswith("_"):
        sp[0] = sp[0][1:]
    if len(sp) < 2:
        raise querymod.RequestError("You must provide a full tag name with saveframe included. For example: Entry.Experimental_method_subtype")

    # We don't know if this is an "ID" or "Entry_ID" saveframe...
    result = querymod.select(['Entry_ID'], sp[0], where_dict={sp[1]:tag_value},
                             modifiers=['lower'], schema=schema)

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
                                                 database=request.args.get('database', 'macromolecules')))

@application.route('/software/name_suggestions')
@application.route('/software/name_suggestions/<database>')
def get_software_suggestions(database="macromolecules"):
    """ Returns new software name suggestions. """

    return Response(querymod.suggest_new_software_links(database=database), mimetype="text/csv")

@application.route('/instant')
def get_instant():
    """ Do the instant search. """

    if not request.args.get('term', None):
        raise querymod.RequestError("You must specify the search term using ?term=search_term")

    return jsonify(querymod.get_instant_search(term=request.args.get('term')))

@application.route('/status')
def get_status():
    """ Returns the server status."""

    return jsonify(querymod.get_status())

# Queries that run commands
@application.route('/validate/')
@application.route('/validate/<entry_id>')
def validate_entry(entry_id=None):
    """ Returns the validation report for the given entry. """

    if not entry_id:
        raise querymod.RequestError("You must specify the entry ID.")

    return jsonify(querymod.get_chemical_shift_validation(ids=entry_id))
