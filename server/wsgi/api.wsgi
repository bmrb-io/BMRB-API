#!/usr/bin/python

import os
import sys
import json
import logging
logging.basicConfig()
from werkzeug.wrappers import Request, Response

# Set up paths for imports and such
local_dir = os.path.dirname(__file__)
os.chdir(local_dir)
sys.path.append(local_dir)

# Local
from utils import querymod
from utils.jsonrpc import JSONRPCResponseManager, dispatcher

@Request.application
def application(request):

    # Handle RESTful queries differently than JSON-RPC queries
    if request.method == "GET" and request.path.startswith("/rest/"):

        request_params = request.path[6:].split("/")

        if request_params[0] == "list_entries":
            message = querymod.list_entries()
        elif request_params[0] == "chemical_shifts":
            message = querymod.get_fields_by_fields(["Entry_ID","Entity_ID","Comp_index_ID","Comp_ID","Atom_ID","Atom_type","Val","Val_err","Ambiguity_code","Assigned_chem_shift_list_ID"], "Atom_chem_shift", as_hash=False)
        elif request_params[0] == "loop":
            message = querymod.get_loops(ids=request_params[1], keys=request_params[2:])
        elif request_params[0] == "entry":
            try:
                message = querymod.get_entries(ids=request_params[1])[request_params[1]]
            except KeyError:
                message = {}
        elif request_params[0] == "raw_entry":
            entry = querymod.get_pickled_entry(request_params[1])
            return Response(entry, mimetype='application/octet-stream')
        elif request_params[0] == "saveframe":
            message = querymod.get_saveframes(ids=request_params[1], keys=request_params[2:])
        elif request_params[0] == "tag":
            message = querymod.get_tags(ids=request_params[1], keys=request_params[2:])
        else:
            message = "Unknown method."

        return Response(json.dumps(message), mimetype='application/json')

    # REDIS driven queries
    dispatcher["tag"] = querymod.get_tags
    dispatcher["loop"] = querymod.get_loops
    dispatcher["saveframe"] = querymod.get_saveframes
    dispatcher["entry"] = querymod.get_entries
    dispatcher["list_entries"] = querymod.list_entries

    # Database driven queries
    dispatcher["select"] = querymod.process_select

    # Process the query
    response = JSONRPCResponseManager.handle(request.get_data(cache=False, as_text=True), dispatcher)
    return Response(response.json, mimetype='application/json')
