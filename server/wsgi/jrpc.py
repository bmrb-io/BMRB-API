#!/usr/bin/python

import logging
from werkzeug.wrappers import Request, Response
from jsonrpc import JSONRPCResponseManager, dispatcher

# Local
import sys
sys.path.append("/websites/webapi/wsgi/utils")
import querymod

logging.basicConfig()

@Request.application
def application(request):

    # Handle RESTful queries differently than JSON-RPC queries
    if request.method == "GET" and request.script_root == "/rest":
        return Response(str(request.script_root)+"\n"+"\n".join(dir(request)), mimetype='application/json')

    # REDIS driven queries
    dispatcher["tag"] = querymod.get_tags
    dispatcher["loop"] = querymod.get_loops
    dispatcher["saveframe"] = querymod.get_saveframes
    dispatcher["entry"] = querymod.get_entries

    # Database driven queries
    dispatcher["select"] = querymod.process_select

    # Process the query
    response = JSONRPCResponseManager.handle(request.get_data(cache=False, as_text=True), dispatcher)
    return Response(response.json, mimetype='application/json')
