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

### JSON-RPC methods

#### list_entries

This query returns a list of all of the valid BMRB entry IDs. There is an
optional parameter - `database` whose value should either be `metabolomics` or
`macromolecule`. If the `database` paramater is supplied than only entries of
the given type will be returned.

An example query:

```json
{
    "method": "list_entries",
    "jsonrpc": "2.0",
    "params": {"database": "macromolecule"},
    "id": 1
}
```

An example response:

```json
{
    "jsonrpc": "2.0",
    "id": 1,
    "result": ["bmse000001", "bmse000002", "bmse000003", ...],
}
```

#### entry

This query returns the BMRB entry in JSON format.








{'database': 'metabolomics', 'query': {'where': {'Descriptor': '%1S/C6H10N2O2/c1-4-7-3-2-5(8-4)6(9)10/h5H,2-3H2,1H3,(H,7,8)(H,9,10)/t5-/m0/s1%'}, 'select': '*', 'hash': False, 'from': 'Chem_comp_descriptor'}}
