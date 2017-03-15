## REST API

All queries return results in JSON format.

#### Databases

The BMRB API has 4 databases. They are:

* `macromolecules` - The standard BMRB database. Contains macromolecules.
* `metabolomics` - The metabolomics database.
* `chemcomps` - The chemical compounds used by the PDB in NMR-STAR format. Note
that these entries only have chemical shifts.
* `combined` - A meta database that searches the three databases above.

Note that not all databases contain the same tables. A search in a table that
a given database doesn't contain will not produce an error; instead it will
return that no results were found.

Queries use the `macromolecules` database by default.

Query types that work on an entry-basis do not need to specify a database as all
databases are searched for those query types.

### REST API queries

#### /status/

Returns the current status of the databases. This includes the number of entries
in each database, the number of chemical shifts in each database, and the last
time each database was updated. The available REST and JSON-RPC methods are also
returned, as well as the version number of the API.

#### /list_entries/[metabolomics|macromolecule|chemcomps]

Returns a list of all entries.
[Here](http://webapi.bmrb.wisc.edu/current/rest/list_entries/)
is an example.
Adding
[/macromolecule/](http://webapi.bmrb.wisc.edu/current/rest/list_entries/macromolecule)
or
[/metabolomics/](http://webapi.bmrb.wisc.edu/current/rest/list_entries/metabolomics)
or
[/chemcomps/](http://webapi.bmrb.wisc.edu/current/rest/list_entries/chemcomps)
at the end will only return the entries of that type.

#### /entry/ - Store entry (POST)

When you access this URI you must also provide a NMR-STAR entry in text format
as the body of the request. The entry will be parsed and stored in the database.
You can then use all of the entry-based queries below on your saved entry. The
response to this request will include two keys:

* `entry_id`: The unique key assigned to your submission. You can then use this
key as the `ENTRY_ID` for the queries below.
* `expiration`: The unix time that the entry will be removed from the database.
This is set as a week after upload. Uploading the same exact file will reset the
expiration to a week from the present time. The expiration date will also be
reset to a week from the present time each you make a request to the API that
uses the provided `ENTRY_ID`. (For example, fetching the entry with `/entry/ENTRY_ID`
will reset the expiration.)

*Caution* - Data you upload to the server is publicly accessibly to anyone with
access to the assigned `ENTRY_ID` you are provided.

#### /entry/$ENTRY_ID[/$ENTRY_FORMAT] - Retrieve entry (GET)

Returns the given BMRB entry in [JSON format](ENTRY.md#entry) by default. If
$ENTRY_FORMAT is specified then return in that format instead.

Only `json` and `nmrstar` are currently allowed for $ENTRY_FORMAT.

[Here](http://webapi.bmrb.wisc.edu/current/rest/entry/15000/) is an example.

#### /saveframe/$ENTRY_ID/$SAVEFRAME_CATEGORY[/$ENTRY_FORMAT]

Returns all saveframes of the given category for an entry in
[JSON format](ENTRY.md#saveframe) by default. If $ENTRY_FORMAT is specified then
return in that format instead.

Only `json` and `nmrstar` are currently allowed for $ENTRY_FORMAT.

[Here](http://webapi.bmrb.wisc.edu/current/rest/saveframe/15000/assigned_chemical_shifts)
is an example query.

#### /loop/$ENTRY_ID/$LOOP_CATEGORY[/$ENTRY_FORMAT]

Returns all loops of a given category for a given entry in
[JSON format](ENTRY.md#loop) by default. If $ENTRY_FORMAT is specified then
return in that format instead.

Only `json` and `nmrstar` are currently allowed for $ENTRY_FORMAT.

[Here](http://webapi.bmrb.wisc.edu/current/rest/loop/15000/_Sample_condition_variable)
is an example query.

#### /tag/$ENTRY_ID/$TAG_NAME

Returns tags of a specified type for a given entry.
[Here](http://webapi.bmrb.wisc.edu/current/rest/tag/15000/_Entry.Title)
is an example.

#### /enumerations/$TAG_NAME

Returns a list of values suggested for the tag in the `values` key if there are
saved enumerations for the tag. In the `type` key one of the following values will
appear:

* `common` - The tag values returned are common values but are not the only legal
values for the tag.
* `enumerations` - The tag values returned are the only legal values for the tag.
* `null` - There are no saved enumerations for the tag.

#### /get_id_from_search/$TAG_NAME/$TAG_VALUE[/$DATABASE]

Returns a list of BMRB entry IDs which contain the specified $TAG_VALUE for the
value of at least one instance of tag $TAG_NAME. The search is done
case-insensitively. You may optionally specify a database if you want
to query the metabolomics database rather than the macromolecule one.

An example:

* [All entries which used solid-state NMR](http://webapi.bmrb.wisc.edu/current/rest/get_id_from_search/Entry.Experimental_method_subtype/solid-state)

#### /chemical_shifts[/$ATOM_TYPE][/$DATABASE]

Returns all of the chemical shifts in the BMRB for the specified atom type. You
can omit the atom type to fetch all chemical shifts and you can use `*` as a
wild card character. Optionally specify `macromolecule` or `metabolomics` for the
database argument to search a specific database. `macromolecule` is the default.

In addition, the following parameters can be provided using the
[standard notation](https://en.wikipedia.org/wiki/Query_string#Web_forms):

* `atom_id` The chemical element of the atom.
* `comp_id` The residue as a 3 letter code.
* `shift` A specific chemical shift to search for. Uses a default threshold of .03
* `threshold` Only has meaning in conjunction with `shift`. Specifies the search
threshold for a shift.

Examples:

* [All chemical shifts](http://webapi.bmrb.wisc.edu/current/rest/chemical_shifts/)
* [All CA chemical shifts](http://webapi.bmrb.wisc.edu/current/rest/chemical_shifts/CA)
* [All HB* chemical shifts](http://webapi.bmrb.wisc.edu/current/rest/chemical_shifts/HB*)

* [All C1 chemical shifts from metabolomics database](http://webapi.bmrb.wisc.edu/current/rest/chemical_shifts/C1/metabolomics)

#### /software/

Returns a summary of all software packages used in BMRB entries.

#### /software/entry/$ENTRY_ID

Returns a list of all software packages used by a given entry. Each item in the
list of software will be a list with the following four values in order:

* `SOFTWARE_NAME`
* `SOFTWARE_VERSION`
* `SOFTWARE_TASK`
* `SOFTWARE_VENDOR`

#### /software/package/$SOFTWARE_PACKAGE/[$DATABASE]

Returns a list of all entries used by the specified software package. The search
is done case-insensitive and does not require perfect matches. For example,
`SPARK` would match `SPARKY` and `NMRFAM_SPARY`.

