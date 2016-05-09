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
