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

from flask import Flask, request, Response
application = Flask(__name__)

def return_json(unserialized_obj):
    return Response(response=json.dumps(unserialized_obj),
                    mimetype="application/json")

@application.route('/')
def no_params():
    """ Return an error if they have not specified which method type to use."""
    return "No method specified!"

@application.route('/list_entries/')
@application.route('/list_entries/<entry_type>')
def list_entries(entry_type=None):
    """ Return a list of all valid BMRB entries."""

    entries = querymod.list_entries()
    if entry_type == "metabolomics":
        entries = [x for x in entries if x.startswith("bm")]
    elif entry_type == "macromolecule":
        entries = [x for x in entries if not x.startswith("bm")]

    return return_json(entries)

@application.route('/debug')
def debug():
    debug_str = "Secure: " + str(request.is_secure)
    debug_str += "<br>URL: " + str(request.url)
    debug_str += "<br>Method: " + str(request.method)
    debug_str += "<br>Viewing from: " + str(request.remote_addr)
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

@application.route('/pickled_entry/<entry_id>')
def pickled_entry(entry_id):

    if not request.is_secure:
        return return_json({"error": "Entry pickles can only be served over HTTPS. Please go to: %s" % request.url.replace("http:", "https:")})
    else:
        # Return raw entries as octet streams
        entry = querymod.get_pickled_entry(entry_id)
        return Response(entry, mimetype='application/octet-stream')

@application.route('/json_entry/<entry_id>')
def json_entry(entry_id):
    return return_json(querymod.get_json_entry(entry_id))

@application.route('/entry/<entry_id>')
def get_entry(entry_id):
    """ Returns an entry in JSON format."""
    return return_json(querymod.get_entries(ids=entry_id))

@application.route('/saveframe/<entry_id>/<saveframe_name>')
def get_saveframe(entry_id, saveframe_name):
    """ Returns a saveframe in JSON format."""
    return return_json(querymod.get_saveframes(ids=entry_id, keys=saveframe_name))

@application.route('/loop/<entry_id>/<loop_name>')
def get_loop(entry_id, loop_name):
    """ Returns a loop in JSON format."""
    return return_json(querymod.get_loops(ids=entry_id, keys=loop_name))

@application.route('/tag/<entry_id>/<tag_name>')
def get_tag(entry_id, tag_name):
    """ Returns all values for the tag for the given entry."""
    return return_json(querymod.get_tags(ids=entry_id, keys=tag_name))
