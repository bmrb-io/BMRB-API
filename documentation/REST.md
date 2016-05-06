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

#### /chemical_shifts/[$ATOM_TYPE]

Returns all of the chemical shifts in the BMRB for the specified atom type. You
can omit the atom type to fetch all chemical shifts and you can use a * to
symbolize a wildcard character.

* [All chemical shifts](http://webapi.bmrb.wisc.edu/current/rest/chemical_shifts/)
* [All CA chemical shifts](http://webapi.bmrb.wisc.edu/current/rest/chemical_shifts/CA)
* [All HB* chemical shifts](http://webapi.bmrb.wisc.edu/current/rest/chemical_shifts/HB*)
