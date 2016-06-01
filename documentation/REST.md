## REST API

All queries return results in JSON format.

### REST API queries

#### /list_entries/[metabolomics|macromolecule]

Returns a list of all entries.
[Here](http://webapi.bmrb.wisc.edu/current/rest/list_entries/)
is an example.
Adding
[/macromolecule/](http://webapi.bmrb.wisc.edu/current/rest/list_entries/macromolecule)
or
[/metabolomics/](http://webapi.bmrb.wisc.edu/current/rest/list_entries/metabolomics)
at the end will only return the entries of that type.

#### /entry/$ENTRY_ID/[$ENTRY_FORMAT]

Returns the given BMRB entry in [JSON format](ENTRY.md#entry)by default. If
$ENTRY_FORMAT is specified then return in that format instead.

Only `json` and `nmrstar` are currently allowed for $ENTRY_FORMAT.

[Here](http://webapi.bmrb.wisc.edu/current/rest/entry/15000/) is an example.

#### /saveframe/$ENTRY_ID/$SAVEFRAME_CATEGORY/[$ENTRY_FORMAT]

Returns all saveframes of the given category for an entry in
[JSON format](ENTRY.md#saveframe) by default. If $ENTRY_FORMAT is specified then
return in that format instead.

Only `json` and `nmrstar` are currently allowed for $ENTRY_FORMAT.

[Here](http://webapi.bmrb.wisc.edu/current/rest/saveframe/15000/assigned_chemical_shifts)
is an example query.

#### /loop/$ENTRY_ID/$LOOP_CATEGORY/[$ENTRY_FORMAT]

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

#### /chemical_shifts/[$ATOM_TYPE]/[$DATABASE]

Returns all of the chemical shifts in the BMRB for the specified atom type. You
can omit the atom type to fetch all chemical shifts and you can use `*` as a
wildcard character. Optionally specify `macromolecule` or `metabolomics` for the
database argument to search a specific database. `macromolecule` is the default.

* [All chemical shifts](http://webapi.bmrb.wisc.edu/current/rest/chemical_shifts/)
* [All CA chemical shifts](http://webapi.bmrb.wisc.edu/current/rest/chemical_shifts/CA)
* [All HB* chemical shifts](http://webapi.bmrb.wisc.edu/current/rest/chemical_shifts/HB*)

* [All C1 chemical shifts from metabolomics database](http://webapi.bmrb.wisc.edu/current/rest/chemical_shifts/C1/metabolomics)
