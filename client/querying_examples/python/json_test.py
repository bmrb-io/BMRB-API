#!/usr/bin/python

""" Tests the JSON-RPC API."""

# Work in both python2 and 3
from __future__ import print_function

# Imports
import sys
import requests

request_counter = 1

def postIt(method, params=None):

    global request_counter

    if params is None:
        params = {}

    print("Calling method: %s" % method)
    print("Args: %s\n" % params)

    request = {
        "method": method,
        "jsonrpc": "2.0",
        "params": params,
        "id": request_counter
    }

    request_counter += 1

    url = "http://webapi.bmrb.wisc.edu/current/jsonrpc"
    # Take command line input of URL
    if len(sys.argv) > 1:
        url = sys.argv[1]

    r = requests.post(url, json=request)

    try:
        print(r.json())
    except ValueError as e:
        print("You triggered an enhandled server error: " + repr(e))
        print("Response:\n" + r.text)

    print("\n\n")

# Test the chemical_shifts function
postIt("chemical_shifts",
    {
        "atom_type": "C1",
        "database": "metabolomics",
    }
)

# Test the list entries function
postIt("list_entries",
    {
        "database": "metabolomics",
    }
)

# Get all the metabolomics entries that have at least one datum in the
#  Chem_comp_descriptor field
postIt("select",
    {
        "database": "metabolomics",
        "query": {
            "hash": False,
            "select": "*",
            "from": "Chem_comp_descriptor",
            "where": {
                "Descriptor": "%1S/C6H10N2O2/c1-4-7-3-2-5(8-4)6(9)10/h5H,%"
            }
        }
    }
)

# Do a loop query that will fail because ids is not specified
postIt("loop",
    {
        "raw": False,
        "keys": ["_Vendor"]
    }
)

# Do a loop query
postIt("loop",
    {
        "raw": False,
        "ids": [15000, 16000],
        "keys": ["_Vendor"]
    }
)

# Do a raw loop query - get the loop as JSON directly rather than
#  in NMR-STAR format
postIt("loop",
    {
        "raw": True,
        "ids": [15000, 16000],
        "keys": ["_Vendor"]
    }
)

# Test error handling (the ids and "keys" should be wrapped with lists)
postIt("loop",
    {
        "ids": 15000,
        "keys": "_Vendor"
    }
)

# Do a saveframe query - note that you can also get a saveframe in JSON
#  by specifying "raw":True
postIt("saveframe",
    {
        "ids": [15000, 15010],
        "keys": ["sample_conditions"]
    }
)

# Entry query
postIt("entry",
    {
        "raw": False,
        "ids": [15000]
    }
)

# Do a few tag queries
postIt("tag",
    {
        "ids": list(range(15000, 15010)),
        "keys": ["_entry.title", "_citation.title"]
    }
)

postIt("tag",
    {
        "ids": ["bmse001113"],
        "keys": ["Atom_chem_shift.Entry_ID", "Atom_chem_shift.Entity_ID",
                 "Atom_chem_shift.Comp_index_ID", "Atom_chem_shift.Comp_ID",
                 "Atom_chem_shift.Atom_ID", "Atom_chem_shift.Atom_type",
                 "Atom_chem_shift.Val", "Atom_chem_shift.Val_err",
                 "Atom_chem_shift.Ambiguity_code",
                 "Atom_chem_shift.Assigned_chem_shift_list_ID"]
    }
)

# Get all the metabolomics entries that have at least one datum in the
#  Chem_comp_descriptor field
postIt("select",
    {
        "database": "metabolomics",
        "query": {
            "from": "Chem_comp_descriptor"
        }
    }
)

# Do an INCHI query
postIt("select",
    {
        "database": "metabolomics",
        "query": {
            "from": "Chem_comp_descriptor",
            "where": {
                "Type": "INCHI",
                "Descriptor": "%1S/C6H10N2O2/c1-4-7-3-2-5(8-4)6(9)10/h5H,%"
            }
        }
    }
)

# Query the chemical shifts for a specific entry
postIt("select",
    {
        "database":"metabolomics",
        "query": {
            "from": "Atom_chem_shift",
            "select": ["Entry_ID", "Entity_ID", "Comp_index_ID", "Comp_ID",
                       "Atom_ID", "Atom_type", "Val", "Val_err",
                       "Ambiguity_code", "Assigned_chem_shift_list_ID"],
            "where":{
                "Entry_ID": "bmse001100"
            }
        }
    }
)

# Another INCHI query
postIt("select",
    {
        "database": "macromolecules",
        "query": {
            "modifiers":["lower"],
            "from": "Chem_comp_descriptor",
            "where": {
                "Type": "InChI",
                "Descriptor": "%1S/C5H9NO3/c1-3(5(8)9)6-4(2)7/h3H,1-2H3,%"
            }
        }
    }
)

# Do a SMILES query
postIt("select",
    {
        "database": "metabolomics",
        "query": {
            "modifiers":["lower", "count"],
            "from": "Chem_comp_descriptor",
            "where": {
                "Type": "SMILES",
                "Descriptor": "%CC(C)%"
            }
        }
    }
)

# Do a SMILES query
postIt("select",
    {
        "database": "metabolomics",
        "query": {
            "select":['Descriptor'],
            "from": "Chem_comp_descriptor",
            "where":{"Type":"INCHI_KEY"}
        }
    }
)


