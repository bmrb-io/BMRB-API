# BMRB-API

## About

The Biological Magnetic Resonance Bank is developing a hybrid REST/JSON-RPC
API to use for querying against the substantial BMRB databases. Most data in the
macromolecule and metabolomics databases are accessbile through the API.

The API is free to use and doesn't require an API key; though if you submit a
large number of queries you may be rate limited.

The URL of the API is [webapi.bmrb.wisc.edu](http://webapi.bmrb.wisc.edu/). If
you navigate there you will see links to all active versions of the API.

### Why REST and JSON-RPC?

* The REST API exists to make common API requests very easy and straightforward.
* The JSON-RPC API exists to allow the building and submission of complex
queries.

Both APIs return the same results in the same format, with some minor caveats.

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

### Results

Certain queries return results on an entry, saveframe, or loop in JSON format.
To see how we convert our NMR-STAR entries, saveframes, and loops into JSON
format please see the reference [here](documentation/ENTRY.md).

### Rate limiting

We have a rate limit enforced in order to guarantee a responsive API server. It
is unlikely that you will encounter the limit, but if you do you will receive a
HTTP 403 error as a response to all requests. Please ensure to check for this
error in your applications and wait before sending further queries.

If you are blacklisted simply wait at least 10 seconds before sending ANY
queries and you will be removed from the blacklist.

Limits:
* Up to 4 queries of the same resource (URI) per second.
* Up to 50 queries per second of different URIs.

We reserve the right to increase or decrease these limits in the future without
warning.

## REST

Click [here](documentation/REST.md) to view the REST documentation.

## JSON-RPC

Click [here](documentation/JSONRPC.md) to view the JSON-RPC documentation.
