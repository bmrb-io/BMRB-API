#!/usr/bin/python

import logging
# We need to be able to catch the JSONExceptions
from jsonrpc.exceptions import JSONRPCDispatchException as JSONException
from werkzeug.wrappers import Request, Response
# Local
import sys
sys.path.append("/websites/webapi/wsgi/utils")
import querymod

from flask import Flask

logging.basicConfig()

app = Flask(__name__)

@app.route("/inchi/<inchi_search>")
def query_inchi(inchi_search):
    """ Do an InChi search on the string."""

    send = {"database":"metabolomics",
            "query":{
            "from": "Chem_comp_descriptor",
            "where": {
                "Type": "INCHI",
                "Descriptor": inchi_search
            }
        }
    }
    return querymod.process_select(**send)

@app.route("/rest")
def rest():
    return "Alive"

if __name__ == '__main__':
    app.run('0.0.0.0', port=8080)
