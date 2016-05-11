#!/usr/bin/python

""" This code is used to provide the REST API interface. Under the hood
all of the work is done in utils/querymod.py - this just routes the queries
to the correct location and passes the results back."""

import os
import sys
import json
import logging
logging.basicConfig()

# Set up paths for imports and such
local_dir = os.path.dirname(__file__)
os.chdir(local_dir)
sys.path.append(local_dir)

# Import flask
from flask import Flask, request, Response
# Import the functions needed to service requests
from utils import querymod

# Set up the flask application
application = Flask(__name__)

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
def list_entries(entry_type=None):
    """ Return a list of all valid BMRB entries."""

    entries = querymod.list_entries(database=entry_type)
    return return_json(entries)

@application.route('/debug')
def debug(methods=['GET', 'POST']):
    """ This method prints some debugging information. """
    debug_str = "Secure: " + str(request.is_secure)
    debug_str += "<br>URL: " + str(request.url)
    debug_str += "<br>Method: " + str(request.method)
    debug_str += "<br>Viewing from: " + str(request.remote_addr)
    debug_str += "<br>Avail: %s" % dir(request)
    return debug_str

@application.route('/chemical_shifts/')
@application.route('/chemical_shifts/<atom_type>')
@application.route('/chemical_shifts/<atom_type>/<database>')
def chemical_shifts(atom_type=None, database=None):
    """ Return a list of all chemical shifts for the given atom type."""
    return return_json(querymod.get_chemical_shifts(atom_type=atom_type,
                                                    database=database))

@application.route('/entry/<entry_id>/')
def get_entry(entry_id):
    """ Returns an entry in JSON format."""
    return return_json(querymod.get_raw_entry(entry_id), encode=False)

@application.route('/saveframe/<entry_id>/<saveframe_category>')
def get_saveframe(entry_id, saveframe_category):
    """ Returns a saveframe in JSON format."""
    result = querymod.get_saveframes(ids=entry_id, keys=saveframe_category)
    return return_json(result)

@application.route('/loop/<entry_id>/<loop_category>')
def get_loop(entry_id, loop_category):
    """ Returns a loop in JSON format."""
    return return_json(querymod.get_loops(ids=entry_id, keys=loop_category))

@application.route('/tag/<entry_id>/<tag_name>')
def get_tag(entry_id, tag_name):
    """ Returns all values for the tag for the given entry."""
    return return_json(querymod.get_tags(ids=entry_id, keys=tag_name))
