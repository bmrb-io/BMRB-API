## JSON-RPC

### JSON-RPC protocol

First, you may want to take a look at the
[JSON-RPC specification](http://www.jsonrpc.org/specification).
The URL to access the JSON-RPC API is similar to that used to access the REST
API but does not change based on query type or paramaters. Instead, there is one
fixed URL and all JSON-RPC requests are sent there. Requests to the JSON-RPC API
need to be sent as POST requests rather than GET requests or you will encounter
an error. To find the JSON-RPC URL add jsonrpc to the versioned URL described
[in the main documentation](../README.md#api-urls). For example, the most up to
date version will always be located at
[webapi.wisc.edu/current/jsonrpc](http://webapi.wisc.edu/current/jsonrpc).

Note that JSON-RPC allows submitting multiple queries before receiving the
results. You should look at the JSON-RPC libraries available
[for your language](https://en.wikipedia.org/wiki/JSON-RPC#Implementations).

#### A quick summary of JSON-RPC for those who don't read the documentation

Each JSON-RPC query is submitted in JSON format, and must be a dictionary
containing the following keys:

* `method` - The method. Determines what parameters are valid and what result is
generated.
* `id` - Any legal string or numerical value which is used in the response to link
the request to the corresponding response. (Remember you may submit multiple
queries in parallel.)
* `jsonrpc` - The version of JSON-RPC used for the query. This should always be
set to `2.0`.
* `params` - The parameters of your query. This will always be a dictionary of
paramater_name -> parameter_value. Many of the query types support lists for the
values of the parameters.

Each JSON-RPC response will contain the following keys:

* `results` - The results of the query. Will be `null` if an error occured.
* `error` - A description of an error in dictionary format. Will not be present
if no error occured.
  * `code` - The error code. Refer to the
  [specification](http://www.jsonrpc.org/specification#error_object).
  * `message` - A string description of the error.
* `id` - The same id included in the request mirrored back.

The contents of the `params` and `response` keys will be detailed for the
individual methods below.

#### Databases

The BMRB API has 4 databases. They are:

* `macromolecules` - The standard BMRB database. Contains macromolecules.
* `metabolomics` - The metabolomics database.
* `chemcomps` - The chemical compounds used by the PDB in NMR-STAR format. Note
that these entries only have no chemical shifts.
* `combined` - A meta database that searches the three databases above.

Note that not all databases contain the same tables. A search in a table that
a given database doesn't contain will not produce an error; instead it will
return that no results were found. At this point the `select` query cannot
operate on the `combined` database, but all other queries can.

If a query does not provide a database the combined database is used except for
the `select` query which uses the `macromolecules` database. We are working on
supporting the combined database for `select` queries.

Query types that work on an entry-basis do not need to specify a database as all
databases are searched for those query types.

### JSON-RPC methods

#### status

Returns the current status of the databases. This includes the number of entries
in each database, the number of chemical shifts in each database, and the last
time each database was updated. The available REST and JSON-RPC methods are also
returned, as well as the version number of the API.

Paramters: None

Example query:

```json
{
    "method": "status",
    "jsonrpc": "2.0",
    "params": {},
    "id": 1
}
```

Example response:

```json
{   "jsonrpc": "2.0",
    "result": {
        "macromolecules": {
            "update_time": 1466603754.191061,
            "num_entries": 10847.0,
            "num_chemical_shifts": 8100700.0
        },
        "chemcomps": {
            "update_time": 1466603768.02896,
            "num_entries": 21221.0
        },
        "metabolomics": {
            "update_time": 1466603752.659468,
            "num_entries": 1298.0,
            "num_chemical_shifts": 27598.0
        },
        "combined": {
            "update_time": 1466603807.872188,
            "num_entries": 33366.0
        },
        "version": "v0.4.3",
        "jsonrpc_methods": ["tag", "loop", "saveframe", "entry", "list_entries", "chemical_shifts", "select", "status"],
        "rest_methods": ["list_entries", "chemical_shifts", "entry", "saveframe", "loop", "tag", "status"]
    },
    "id": 1
}
```

#### list_entries

This query returns a list of all of the valid BMRB entry IDs.

Optional parameters:
* `database` - Which database to search. See [databases](#databases).

Example query (returns a list with all valid macromolecule BMRB IDs):

```json
{
    "method": "list_entries",
    "jsonrpc": "2.0",
    "params": {"database": "macromolecule"},
    "id": 1
}
```

Example response:

```json
{
    "jsonrpc": "2.0",
    "id": 1,
    "result": ["bmse000001", "bmse000002", "bmse000003", "..."],
}
```

#### chemical_shifts

This query returns all chemical shifts. Allows filtering by atom type and
database.

Optional parameters:
* `database` - Which database to search. See [databases](#databases).
* `atom_type` - A string specifying which atom type to query for. `*` is
interpreted as a wildcharacter. Specifying `HB*` would search for all `HB`
shifts.

By default all macromolecule chemical shifts are returned.

Example query (returns a list of all shifts as lists from the metabolomics
database):

```json
{
    "method": "chemical_shifts",
    "jsonrpc": "2.0",
    "params": {"database": "metabolomics"},
    "id": 1
}
```

Example response:

```json
{
    "jsonrpc": "2.0",
    "result": {
        "data": [
            ["bmse000001", 1, 1, "1", "C1", "C", "39.309", null, 1, 1],
            ["bmse000001", 1, 1, "1", "C2", "C", "27.664", null, 1, 1],
            ["..."]
        ],
        "columns": [
            "Atom_chem_shift.Entry_ID", "Atom_chem_shift.Entity_ID",
            "Atom_chem_shift.Comp_index_ID", "Atom_chem_shift.Comp_ID",
            "Atom_chem_shift.Atom_ID", "Atom_chem_shift.Atom_type",
            "Atom_chem_shift.Val", "Atom_chem_shift.Val_err",
            "Atom_chem_shift.Ambiguity_code",
            "Atom_chem_shift.Assigned_chem_shift_list_ID"
        ]
    },
    "id": 1
}
```

#### entry

This query returns the queried BMRB entr(y|ies) in JSON format. Unlike the REST
API, you may query up to 500 entries simultaneously.

Mandatory parameters:
* `ids`: A list of BMRB IDs to return.

Optional parameters:
* `format`: Either `nmrstar` to return the entry in NMR-STAR format or `json` to
return the entry in JSON format.

Example query (returns the full BMRB entries 15000 and 16000):

```json
{
    "method": "entry",
    "jsonrpc": "2.0",
    "params": {
        "format": "json",
        "ids": [15000, 16000]
    },
    "id": 1
}
```

Example response:

```json
{
    "jsonrpc": "2.0",
    "id": 1,
    "result": {
        "15000":{},
        "16000":{}
    },
}
```

Note that in the above example the `{}`s will actually contain the BMRB entries
in JSON format. For more information on BMRB entry JSON format, please see the
[dedicated page](documentation/ENTRY.md).

#### saveframe

This query returns the queried BMRB saveframe(s) in
[JSON format](documentation/ENTRY.md#saveframe). Unlike the REST
API, you may query an unlimited number of saveframes from up to 500 entries
simultaneously.

Mandatory parameters:
* `ids`: A list of BMRB IDs to search for the specified saveframes.
* `keys`: A list of the saveframes you want returned from each of the specified
entries.

Optional parameters:
* `format`: Either `nmrstar` to return the saveframe in NMR-STAR format or `json`
to return the saveframe in JSON format.

Example query (returns all saveframes of category "sample_conditions" from the
BMRB entries 15000 and 16000):

```json
{
    "method": "saveframe",
    "jsonrpc": "2.0",
    "params": {
        "ids": [15000, 16000],
        "keys": ["sample_conditions"]
    },
    "id": 1
}
```

Example response:

```json
{
    "jsonrpc": "2.0",
    "id": 1,
    "result": {
        "jsonrpc": "2.0",
        "result": {
            "15010": {
                "sample_conditions": [{},{}]
            },
            "15000": {
                "sample_conditions": [{}, {}]
            }
        }
    }
}
```

Note that in the above example the `{}`s will actually contain the saveframes in
JSON format.

#### loop

This query returns the queried BMRB loop(s) in JSON format. Unlike the REST
API, you may query an unlimited number of loops from up to 500 entries
simultaneously.

Mandatory parameters:
* `ids`: A list of BMRB IDs to search for the specified loops.
* `keys`: A list of the loops you want returned from each of the specified
entries.

Optional parameters:
* `format`: Either `nmrstar` to return the loops in NMR-STAR format or
`json` to return the loops in JSON format.

Example query (returns all loops of category "Vendor" from the BMRB entries
15000 and 16000):

```json
{
    "method": "loop",
    "jsonrpc": "2.0",
    "params": {
        "ids": [15000, 16000],
        "keys": ["_Vendor"]
    },
    "id": 1
}
```

Example response:

```json
{
    "jsonrpc": "2.0",
    "id": 1,
    "result": {
        "jsonrpc": "2.0",
        "result": {
            "15010": {
                "_Vendor": [{},{}]
            },
            "15000": {
                "_Vendor": [{}, {}]
            }
        }
    }
}
```

Note that in the above example the `{}`s will actually contain the loops in
JSON format.

#### tag

Returns all specified tags for all the specified entries.

Mandatory parameters:
* `ids`: A list of BMRB IDs to search for the specified tags.
* `keys`: A list of the tags you want returned from each of the specified
entries. You must specify the full tag - for example, `_Entry.Title` is valid,
but `Title` is not because the server will not know which saveframe to look for
the tag in. Note that capitalization is not important but the key in the results
sent back to you will use the same capitalization that you used in the request.

Example query (returns the entry title for entries 15000 and 16000):

```json
{
    "method": "tag",
    "jsonrpc": "2.0",
    "params": {
        "ids": [15000, 16000],
        "keys": ["_Entry.Title"]
    },
    "id": 1
}
```

Example response:

```json
{
    "jsonrpc": "2.0",
    "result": {
        "16000": {
            "_Entry.Title": ["Solution structure of the nucleocapsid-binding domain of the measles virus phosphoprotein\n"]
        },
        "15000": {
            "_Entry.Title": ["Solution structure of chicken villin headpiece subdomain containing a fluorinated side chain in the core\n"]
        }
    },
    "id": 1
}
```

#### select

This query allows you to perform a SELECT query against the BMRB relational
database with an arbitrary number of selectors. It allows you to get any number
of tags from a given saveframe type, or any number of tags from a given loop
type - with optional filters applied to the results.

Mandatory parameters:
* `query`: A dictionary containing the parameters for the given query.
  * `from`: The name of the table you want to select from. I.e. -
  `Chem_comp_descriptor`.

Optional parameters:
* `database` - Which database to search. See [databases](#databases).
* `query`: Not optional, but the following children are:
  * `modifiers`: A list of modifiers to use. The currently allowed values
  (specified by adding their name as a string to the `modifiers` list) are:
    * `lower`: Performs the filters in a case-insensitive way.
    * `count`: Returns the count of matching results rather than the actual
    results.
  * `select`: A list of columns (tags) that you want to select from the table
  spefified. If you want all of them you can use "*" rather than a list.
  * `where`: A dictionary of as many `key` -> `filter on key` pairs as you want.
  If you don't have the `key` in your `from` paramter, it will automatically be
  added. An example is `Type`: `SMILES` which specifies that the `Type` column
  MUST BE `SMILES` in order to print the result. You can use `%` multiple times
  anywhere in the value as a wildcharacter.
  * `hash`: A boolean. `true` makes the results ordered such that each column is
  a key that points to a list of all of it's values. `false` results in the values
  being returned as a list of rows (as lists).

Example query (returns all tags from the chemical compound descriptor loop where
the `Descriptor` contains (but does not have to be exactly) the value `1S/...`):
```json
{
    "method": "select",
    "jsonrpc": "2.0",
    "params": {
        "database": "metabolomics",
        "query": {
            "where": {
                "Descriptor": "%1S/C6H10N2O2/c1-4-7-3-2-5(8-4)6(9)10/h5H,2-3H2,1H3,(H,7,8)(H,9,10)/t5-/m0/s1%"
            },
            "select": "*",
            "hash": false,
            "from": "Chem_comp_descriptor"
        }
    },
    "id": 1
}
```

Response:

```json
{
    "jsonrpc": "2.0",
    "result": {
        "columns": [
            "Chem_comp_descriptor.Descriptor",
            "Chem_comp_descriptor.Type",
            "Chem_comp_descriptor.Program",
            "Chem_comp_descriptor.Program_version",
            "Chem_comp_descriptor.Sf_ID",
            "Chem_comp_descriptor.Entry_ID",
            "Chem_comp_descriptor.Comp_ID"
        ],
        "data": [
            ["InChI=1S/C6H10N2O2/c1-4-7-3-2-5(8-4)6(9)10/h5H,2-3H2,1H3,(H,7,8)(H,9,10)/t5-/m0/s1", "INCHI", "OpenBabel", "2.3.2", 20182, "bmse001100", "BMET001100"],
            ["InChI=1S/C6H10N2O2/c1-4-7-3-2-5(8-4)6(9)10/h5H,2-3H2,1H3,(H,7,8)(H,9,10)/t5-/m0/s1", "INCHI", "PUBCHEM_IUPAC", "na", 20182, "bmse001100", "BMET001100"],
            ["InChI=1S/C6H10N2O2/c1-4-7-3-2-5(8-4)6(9)10/h5H,2-3H2,1H3,(H,7,8)(H,9,10)/t5-/m0/s1", "INCHI", "RDKit", "2015.09.2", 20182, "bmse001100", "BMET001100"]
        ]
    },
    "id": 1
}
```

### Example code

It is very simple to send queries to the server using Python and the requests
module. If you don't have the requests module installed run:

```bash
sudo pip install requests
```

Here is an example which queries for 500 BMRB entries in a loop:

```python

import time
import requests

for x in range(15000,15100):

    entry_request = {
        "method": "entry",
        "jsonrpc": "2.0",
        "params": {"ids": [x]},
        "id": x
    }

    response = requests.post("http://webapi.bmrb.wisc.edu/current/jsonrpc",
                           json=entry_request)

    if response.status_code == 403:
        print "Waiting to continue because of rate limiting."
        time.sleep(10)
        response = requests.get("http://webapi.bmrb.wisc.edu/current/jsonrpc",
                           json=entry_request)

    if response.status_code != 200:
        print "Server error: %s" % response.text
        continue

    try:
        bmrb_entry = response.json()
        print bmrb_entry.keys(), bmrb_entry['result'].keys()
    except Exception as e:
        print "Exception occured: %s" % str(e)
```
