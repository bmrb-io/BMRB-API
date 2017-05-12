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
time each database was updated. The available REST methods are also
returned, as well as the version number of the API.

[Link](http://webapi.bmrb.wisc.edu/v1/rest/status)

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

*Caution* - Data you upload to the server is publicly accessible to anyone with
access to the assigned `ENTRY_ID` you are provided. Therefore you should not
share this key with anyone who you do not intend to share the data with.

#### /entry/$ENTRY_ID[/$ENTRY_FORMAT] - Retrieve entry (GET)

Returns the given BMRB entry in [JSON format](ENTRY.md#entry) by default. If
$ENTRY_FORMAT is specified then return in that format instead.

The formats available are:

* `json` - The default format. Returns the entry in JSON format. [Example](http://webapi.bmrb.wisc.edu/v1/rest/entry/15000/)
* `nmrstar` - The response is still JSON but the entire entry is returned
as one large text string rather than JSON. [Example](http://webapi.bmrb.wisc.edu/v1/rest/entry/15000/nmrstar/)
* `rawnmrstar` - The entry is returned in pure NMR-STAR format. There is
no wrapping JSON. If you need to fetch a large number of NMR-STAR entries
in text form you may be better served getting them from the [FTP site](http://www.bmrb.wisc.edu/ftp/pub/bmrb/entry_directories/). [Example](http://webapi.bmrb.wisc.edu/v1/rest/entry/15000/rawnmrstar/)
* `zlib` - A zlib-compressed JSON representation of the entry is returned.
This is how the entries are stored in the API database and is therefore the
absolute fastest way to retrieve an entry. This format mainly exists
to enable the [PyNMR-STAR python library](https://github.com/uwbmrb/PyNMRSTAR) to
fetch entries as quickly as possible and it is not expected you will
benefit from the moderately faster entry access considering the additional
code complexity required. [Example](http://webapi.bmrb.wisc.edu/v1/rest/entry/15000/zlib/)

#### /saveframe/$ENTRY_ID/$SAVEFRAME_CATEGORY[/$ENTRY_FORMAT]

Returns all saveframes of the given category for an entry in
[JSON format](ENTRY.md#saveframe) by default. If $ENTRY_FORMAT is specified then
return in that format instead.

Only `json` and `nmrstar` are currently allowed for $ENTRY_FORMAT. These
formats are the same as described in the entry method.

[Here](http://webapi.bmrb.wisc.edu/current/rest/saveframe/15000/assigned_chemical_shifts)
is an example query.

#### /loop/$ENTRY_ID/$LOOP_CATEGORY[/$ENTRY_FORMAT]

Returns all loops of a given category for a given entry in
[JSON format](ENTRY.md#loop) by default. If $ENTRY_FORMAT is specified then
return in that format instead.

Only `json` and `nmrstar` are currently allowed for $ENTRY_FORMAT. These
formats are the same as described in the entry method.

[Here](http://webapi.bmrb.wisc.edu/current/rest/loop/15000/_Sample_condition_variable)
is an example query.

#### /tag/$ENTRY_ID/$TAG_NAME

Returns tags of a specified type for a given entry.
[Here](http://webapi.bmrb.wisc.edu/v1/rest/tag/15000/_Entry.Title)
is an example.

#### /enumerations/$TAG_NAME

Returns a list of values suggested for the tag in the `values` key if there are
saved enumerations for the tag. In the `type` key one of the following values will
appear:

* `common` - The tag values returned are common values but are not the only legal
values for the tag.
* `enumerations` - The tag values returned are the only legal values for the tag.
* `null` - There are no saved enumerations for the tag.

Example: [List of common NMR-STAR versions](http://webapi.bmrb.wisc.edu/v1/rest/enumerations/_Entry.NMR_STAR_version)

You can narrow the results to those starting with the value you provide in the
`term` parameter in the query string. This will return the results in a form
that can be used by JQuery's auto-complete.

Example: [List of common NMR-STAR versions starting with 2](http://webapi.bmrb.wisc.edu/v1/rest/enumerations/_Entry.NMR_STAR_version?term=2)

#### /instant?term=$SEARCH_TERM

This URL powers the BMRB instant search tool. It queries all macromolecule and
metabolomics entries based on a variety of commonly searched fields. It does exact
searches on certain fields and fuzzy-matches on others depending on what is most
appropriate for the field (for example, database matches must be exact but InChI
matches may be similar). It returns matches sorted by what results it thinks are
the most relevant. It should always begin sending results within 1 second to allow
you to use it in interactive applications. A non-exhaustive list of the search fields:

* Title
* Citation Title
* Authors
* Entry ID
* Related Database Codes
* Organism name (common and scientific)
* InChI string and SMILES string (for metabolomics entries)
* Formula (for metabolomics entries)
* Sequence (for macromolecule entries)
* Citation DOI
* Additional data available (e.g. residual dipolar couplings)

You can use this endpoint to do a "general search" against the entire BMBR
archive. [Example link for "john markley mouse"](http://webapi.bmrb.wisc.edu/v1/rest/instant/?term=john%20markley%20mouse).
It will return results that can be used by JQuery auto-complete with some additional fields provided. This means
it returns a list of dictionaries, each of which corresponds to one matching entry.
Entries are only listed once even if multiple fields matches. The entry
dictionaries will always contain the following keys:

* `sub_date` - The date of submission of the entry. YYY-MM-DD format.
* `value` - The unique BMRB entry ID. Could be a macromolecule or metabolomics
ID. (e.g. 15000 or bmse000001)
* `label` - The title of the entry.
* `citation` - A list of citation titles for the entry.
* `link` - A relative link (relative to the BMRB home page) pointing to the URL
this entry can be accessed at. Always use this value (appended to www.bmrb.wisc.edu)
rather than constructing the URL yourself since some results returned link to non-entry
summary pages. (For example, on-hold entries appear in the results if searched by ID.
their link points to the "on hold entries" page at BMRB.)
* `authors` - The list of authors for this entry.

If the search matched one of the "additional" search fields (any field other than
ID, Title, Author and Citation) the key `extra` will also exist and point to another
dictionary. That dictionary contains the following two keys:

* `termname` - The name of the field that the search matched. (e.g. organism scientific name)
* `term` - The value of the matching field value from the BMRB entry.

#### /get_id_from_search/$TAG_NAME/$TAG_VALUE[/$DATABASE]

Returns a list of BMRB entry IDs which contain the specified $TAG_VALUE for the
value of at least one instance of tag $TAG_NAME. The search is done
case-insensitively. You may optionally specify a database if you want
to query the metabolomics database rather than the macromolecule one.

An example:

* [All entries which used solid-state NMR](http://webapi.bmrb.wisc.edu/v1/rest/get_id_from_search/Entry.Experimental_method_subtype/solid-state)

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

* [All chemical shifts](http://webapi.bmrb.wisc.edu/v1/rest/chemical_shifts/)
* [All CA chemical shifts](http://webapi.bmrb.wisc.edu/v1/rest/chemical_shifts/CA)
* [All HB* chemical shifts](http://webapi.bmrb.wisc.edu/v1/rest/chemical_shifts/HB*)
* [All C1 chemical shifts from metabolomics database](http://webapi.bmrb.wisc.edu/v1/rest/chemical_shifts/C1/metabolomics)
* [All C chemical shifts between 130 and 131 ppm](http://webapi.bmrb.wisc.edu/v1/rest/chemical_shifts/C?shift=130.5&threshold=.5)

#### /software/

Returns a summary of all software packages used in BMRB entries. [Link](http://webapi.bmrb.wisc.edu/v1/rest/software/)

#### /software/entry/$ENTRY_ID

Returns a list of all software packages used by a given entry. Each item in the
list of software will be a list with the following four values in order:

* `SOFTWARE_NAME`
* `SOFTWARE_VERSION`
* `SOFTWARE_TASK`
* `SOFTWARE_VENDOR`

[Example for entry 15000](http://webapi.bmrb.wisc.edu/v1/rest/software/entry/15000/)

#### /software/package/$SOFTWARE_PACKAGE/[$DATABASE]

Returns a list of all entries used by the specified software package. The search
is done case-insensitive and does not require perfect matches. For example,
`SPARK` would match `SPARKY` and `NMRFAM_SPARY`.

[Example for SPARKY](http://webapi.bmrb.wisc.edu/v1/rest/software/package/sparky/macromolecules)
