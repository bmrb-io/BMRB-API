# BMRB-API

## About

The Biological Magnetic Resonance Bank is developing a hybrid REST/JSON-RPC
API to use for querying against the substantial BMRB databases. Most data in the
macromolecule and metabolomics databases are accessbile through the API.

The API is free to use and doesn't require an API key; though if you submit a
large number of queries you may be rate limited.

The URL of the API is [webapi.bmrb.wisc.edu](http://webapi.bmrb.wisc.edu/)

### Why REST and JSON-RPC?

* The REST API exists to make common API requests very easy and straightforward.
* The JSON-RPC API exists to allow the building and submission of complex
queries.

Both APIs return the same results in the same format.

### Versioning

New API releases will be available at a unique URL so that you can continue to
rely on a given API version as we continue to improve and develop the API.
We intend to keep each released version of the API live as long as is feasible.

### API URLs

From the root of the API server, first add the version you want to query. For
example, [webapi.bmrb.wisc.edu/v0.2/](http://webapi.bmrb.wisc.edu/v0.2/) for the
alpha release version v0.2, or
[webapi.bmrb.wisc.edu/current/](http://webapi.bmrb.wisc.edu/current/)
to ensure your query goes to the current API version, whatever that is at the
time.

Then, append either [/rest](http://webapi.bmrb.wisc.edu/current/rest) for the
RESTful interface, or [/jsonrpc](http://webapi.bmrb.wisc.edu/current/jsonrpc)
for the JSON-RPC interface.

HTTPS is available, though due to the overhead in establishing a TLS session,
slightly slower.

### REST API queries

All queries return results in JSON format.

#### /entry/$ENTRY_ID

Returns the given BMRB entry.
[Here](http://webapi.bmrb.wisc.edu/current/rest/entry/15000/) is an example.

#### /saveframe/$ENTRY_ID/$SAVEFRAME_CATEGORY

Returns all saveframes of the given category for an entry.
[Here](http://webapi.bmrb.wisc.edu/current/rest/saveframe/15000/assigned_chemical_shifts)
is an example.

#### /loop/$ENTRY_ID/$LOOP_CATEGORY

Returns all loops of a given category for a given entry.
[Here](http://webapi.bmrb.wisc.edu/current/rest/loop/15000/_Sample_condition_variable)
is an example.

#### /tag/$ENTRY_ID/$TAG_NAME

Returns tags of a specified type for a given entry.
[Here](http://webapi.bmrb.wisc.edu/current/rest/tag/15000/_Entry.Title)
is an example.

#### /list_entries/[metabolomics|macromolecule]

Returns a list of all entries.
[Here](http://webapi.bmrb.wisc.edu/current/rest/list_entries/)
is an example.\
Adding
[/macromolecule/](http://webapi.bmrb.wisc.edu/current/rest/list_entries/macromolecule)
or
[/metabolomics/](http://webapi.bmrb.wisc.edu/current/rest/list_entries/metabolomics)
at the end will only return the entries of that type.

#### /chemical_shifts/[$ATOM_TYPE]

Returns all of the chemical shifts in the BMRB for the specified atom type. You
can omit the atom type to fetch all chemical shifts and you can use a * to
symbolize a wildcard character.

* [All chemical shifts](http://webapi.bmrb.wisc.edu/current/rest/chemical_shifts/)
* [All CA chemical shifts](http://webapi.bmrb.wisc.edu/current/rest/chemical_shifts/CA)
* [All HB* chemical shifts](http://webapi.bmrb.wisc.edu/current/rest/chemical_shifts/HB*)


