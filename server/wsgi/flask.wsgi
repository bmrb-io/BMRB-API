#!/usr/bin/python

import os
import sys
import json
import logging
logging.basicConfig()

# Set up paths for imports and such
local_dir = os.path.dirname(__file__)
os.chdir(local_dir)
sys.path.append(local_dir)

# Local
from utils import querymod
from utils.jsonrpc import JSONRPCResponseManager, dispatcher

# Set up flask
from flask import Flask, request, Response
from flask_restful import Resource, Api
application = Flask(__name__)
api = Api(application)


todos = {}

class TodoSimple(Resource):
    def get(self, todo_id):
        return {todo_id: todos[todo_id]}

    def put(self, todo_id):
        todos[todo_id] = request.form['data']
        return {todo_id: todos[todo_id]}

api.add_resource(TodoSimple, '/<string:todo_id>')


def return_json(obj, encode=True):
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
def debug():
    debug_str = "Secure: " + str(request.is_secure)
    debug_str += "<br>URL: " + str(request.url)
    debug_str += "<br>Method: " + str(request.method)
    debug_str += "<br>Viewing from: " + str(request.remote_addr)
    debug_str += "<br>Avail: %s" % dir(request)
    return debug_str

@application.route('/chemical_shifts/')
@application.route('/chemical_shifts/<atom_type>')
def chemical_shifts(atom_type=None):
    """ Return a list of all chemical shifts for the given atom type."""

    # Create the search dicationary
    wd = {}
    if atom_type != None:
        wd["Atom_ID"] = atom_type.replace("*", "%")

    chem_shift_fields = ["Entry_ID", "Entity_ID", "Comp_index_ID", "Comp_ID", "Atom_ID", "Atom_type", "Val", "Val_err", "Ambiguity_code", "Assigned_chem_shift_list_ID"]
    return return_json(querymod.get_fields_by_fields(chem_shift_fields, "Atom_chem_shift", as_hash=False, where_dict=wd))

@application.route('/entry/<entry_id>/')
def get_entry(entry_id):
    """ Returns an entry in JSON format."""
    return return_json(querymod.get_raw_entry(entry_id), encode=False)

@application.route('/saveframe/<entry_id>/<saveframe_category>')
def get_saveframe(entry_id, saveframe_category):
    """ Returns a saveframe in JSON format."""
    return return_json(querymod.get_saveframes(ids=entry_id, keys=saveframe_category))

@application.route('/loop/<entry_id>/<loop_category>')
def get_loop(entry_id, loop_category):
    """ Returns a loop in JSON format."""
    return return_json(querymod.get_loops(ids=entry_id, keys=loop_category))

@application.route('/tag/<entry_id>/<tag_name>')
def get_tag(entry_id, tag_name):
    """ Returns all values for the tag for the given entry."""
    return return_json(querymod.get_tags(ids=entry_id, keys=tag_name))
