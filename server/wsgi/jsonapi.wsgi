#!/usr/bin/python

""" This code is used to provide the JSON-RPC API interface. Under the hood
all of the work is done in utils/querymod.py - this just routes the queries
to the correct location and passes the results back."""

import os
import sys
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
    """ Services one request. Called by wsgi module in apache."""

    # REDIS driven queries
    dispatcher["tag"] = querymod.get_tags
    dispatcher["loop"] = querymod.get_loops
    dispatcher["saveframe"] = querymod.get_saveframes
    dispatcher["entry"] = querymod.get_entries
    dispatcher["list_entries"] = querymod.list_entries

    # Database driven queries
    dispatcher["select"] = querymod.process_select

    # Process the query
    request_data = request.get_data(cache=False, as_text=True)
    response = JSONRPCResponseManager.handle(request_data, dispatcher)
    return Response(response.json, mimetype='application/json')
