# BMRB-API

## About

The Biological Magnetic Resonance Bank is developing a REST API to use
for querying against the substantial BMRB databases. Most data in the
macromolecule and metabolomics databases is accessible through the API.

While the API is free to use and doesn't require an API key, if you
submit a large number of queries you may be rate limited.

The URL of the API is [webapi.bmrb.wisc.edu](http://webapi.bmrb.wisc.edu/). If
you navigate there you will see links to all active versions of the API.

### Versioning

New API releases will be available at a unique URL so that you can continue to
rely on a given API version as we continue to improve and develop the API.
We intend to keep each released version of the API live as long as is feasible.

Releases will be named with a major and minor version and optionally a revision
number. For example, the current release version is v1.2. This means that
it is the 1st API version and there have been two minor releases.

Major release version incrementing means that the API may have changed in a way
that breaks existing queries. Therefore you should write your applications to
use a specific major version and only change the URL you query once you are sure
your application is up to date with any changes.

Minor release version incrementing means that new features may have been
released but the API should still be perfectly backwards compatible. As a result
our release URLs will not include the minor release version.

Revision numbers incrementing means that bugs have been patched but no other
substantial changes to the API have been made.

### API URLs

From the root of the API server, first add the version you want to query. For
example, [webapi.bmrb.wisc.edu/v2/](http://webapi.bmrb.wisc.edu/v2/) for the
release version v2, or
[webapi.bmrb.wisc.edu/current/](http://webapi.bmrb.wisc.edu/current/)
to ensure your query goes to the current API version, whatever that is at the
time. It is suggested that you use the /current/ version for development
and a fixed version for software releases. This will ensure that your
deployed applications do not break if a new API version is released.

HTTPS is available, though due to the overhead in establishing a TLS session,
slightly slower. It is only recomended if you are uploading private data
to the server or calling methods on previously uploaded data.

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
* Up to 50 queries per second per IP.

We reserve the right to increase or decrease these limits in the future without
warning.

If you need to perform a lot of queries and the rate limit is a problem
for you please contact us at <bmrbhelp@bmrb.wisc.edu> to get an exception.

### What we ask of you

If using the API in an application you distribute to others, please include the
HTTP header 'Application' whose value is the name of your application, a space,
and then the version number of your application. This allows us to track API usage
more accurately and determine when we can end-of-life old API versions.
Some examples:

Python:
```python
import requests
requests.get("http://webapi.bmrb.wisc.edu/v2/status", headers={"Application":"My Application"})
```
Curl:
```bash
curl "http://webapi.bmrb.wisc.edu/v2/status" -H 'Application: Curl Script'
```

## REST API

All queries return results in JSON format.

#### Databases

The BMRB API has 3 databases. They are:

* `macromolecules` - The standard BMRB database. Contains macromolecules.
* `metabolomics` - The metabolomics database.
* `chemcomps` - The chemical compounds used by the PDB in NMR-STAR format. Note
that these entries only have chemical shifts.

Note that not all databases contain the same tables. In general, a search in a
table that a given database doesn't contain will not produce an error; instead
it will return that no results were found.

Queries use the `macromolecules` database by default.

Query types that work on an entry-basis do not need to specify a database as all
databases are searched for those query types.

#### Development Tips

To have the JSON returned by any method pretty-printed (whitespace is added to
make the JSON human-readable), just add prettyprint=true to your query.

### Queries

#### Status (GET)

**/status**

Returns the current status of the databases and server. This includes the number
of entries in each database, the number of chemical shifts in each database, and
the last time each database was updated. The available methods are also
returned, as well as the version number of the API.

[Link](http://webapi.bmrb.wisc.edu/v2/status)

#### List entries (GET)

**/list_entries[?database=$database]**

Returns a list of all entries.

Example: [List all entries](http://webapi.bmrb.wisc.edu/v2/list_entries)

Example: [List macromolecule entries](http://webapi.bmrb.wisc.edu/v2/list_entries?database=macromolecules)

Example: [List metabolomics entries](http://webapi.bmrb.wisc.edu/v2/list_entries?database=metabolomics)

Example: [List chemcomp entries](http://webapi.bmrb.wisc.edu/v2/list_entries?database=chemcomps)

#### Store entry (POST)

**/entry/**

When you access this URI you must also provide a NMR-STAR entry in text format
as the body of the request. The entry will be parsed and stored in the database.
You can then use all of the entry-based queries below on your saved entry. The
response to this request will include two keys:

* `entry_id`: The unique key assigned to your submission. You can then use this
key as the `entry_id` for the queries below.
* `expiration`: The unix time that the entry will be removed from the database.
This is set as a week after upload. Uploading the same exact file will reset the
expiration to a week from the present time. The expiration date will also be
reset to a week from the present time each you make a request to the API that
uses the provided `entry_id`. (For example, fetching the entry with "/entry/`entry_id`"
will reset the expiration.)

*Caution* - Data you upload to the server is publicly accessible to anyone with
access to the assigned `entry_id` you are provided. Therefore you should not
share this key with anyone who you do not intend to share the data with.

#### Retrieve entry (GET)

**/entry/$entry_id[?format=$entry_format]**

By default returns the given BMRB entry in [JSON format](ENTRY.md#entry). If
`entry_format` is specified then return in that format instead.

The formats available are:

* `json` - The default format. Returns the entry in JSON format. [Example](http://webapi.bmrb.wisc.edu/v2/entry/15000)
* `nmrstar` - The response is still JSON but the entire entry is returned
as one large text string rather than JSON. [Example](http://webapi.bmrb.wisc.edu/v2/entry/15000?format=nmrstar)
* `rawnmrstar` - The entry is returned in pure NMR-STAR format. There is
no wrapping JSON. If you need to fetch a large number of NMR-STAR entries
in text form you may be better served getting them from the [FTP site](http://www.bmrb.wisc.edu/ftp/pub/bmrb/entry_directories/). [Example](http://webapi.bmrb.wisc.edu/v2/entry/15000?format=rawnmrstar)
* `zlib` - A zlib-compressed JSON representation of the entry is returned.
This is how the entries are stored in the API database and is therefore the
absolute fastest way to retrieve an entry. This format mainly exists
to enable the [PyNMR-STAR python library](https://github.com/uwbmrb/PyNMRSTAR) to
fetch entries as quickly as possible and it is not expected you will
benefit from the moderately faster entry access considering the additional
code complexity required. [Example](http://webapi.bmrb.wisc.edu/v2/entry/15000?format=zlib)

#### Retrieve one or more saveframes (GET)

**/entry/$entry_id?saveframe=$saveframe_category[&format=$entry_format]**

Returns all saveframes of the given category for an entry in
[JSON format](ENTRY.md#saveframe) by default. If `entry_format` is specified then
return in that format instead.

Only `json` and `nmrstar` are currently allowed for `entry_format`. These
formats are the same as described in the entry method.

You may provide the URL parameter saveframe=`saveframe_category` multiple times
to retrieve multiple saveframes.

Example: [Querying for the entry information saveframe](http://webapi.bmrb.wisc.edu/v2/entry/15000?saveframe=entry_information)

Example: [Querying for the entry information and citation saveframes](http://webapi.bmrb.wisc.edu/v2/entry/15000?saveframe=entry_information&saveframe=citations)

#### Retreive one or more loops (GET)

**/entry/$entry_id?loop=$loop_category[&format=$entry_format]**

Returns all loops of a given category for a given entry in
[JSON format](ENTRY.md#loop) by default. If `entry_format` is specified then
return in that format instead.

Only `json` and `nmrstar` are currently allowed for `entry_format`. These
formats are the same as described in the entry method.

You may provide the URL parameter loop=`loop_category` multiple times
to retrieve multiple saveframes.

Example: [Query of the entry author loop](http://webapi.bmrb.wisc.edu/v2/entry/15000?loop=Entry_author)

Example: [Query of the entry author loop and the sample component loop](http://webapi.bmrb.wisc.edu/v2/entry/15000?loop=Entry_author&loop=Sample_component)

#### Retreive one or more tags (GET)

**/entry/$entry_id?tag=$tag**

Returns tags of the specified type(s) for a given entry.

Example: [Fetching the entry title](http://webapi.bmrb.wisc.edu/v2/entry/15000?tag=Entry.Title)

Example: [Fetching the entry title and citation title](http://webapi.bmrb.wisc.edu/v2/entry/15000?tag=Entry.Title&tag=Citation.Title)

#### Fetch information on the NMR experiments (GET)

**/entry/$entry_id/experiments**

Returns information about the NMR experiments for an entry.
The information returned:

* Data files available and their location
* Sample component information
* Sample experimental condition information
* NMR spectrometer information

Example: [Experiments for entry bmse000001](http://webapi.bmrb.wisc.edu/v2/entry/bmse000001/experiments)

#### Get tag enumerations (GET)

**/enumerations/$tag_name[?term=$search_term]**

Returns a list of values suggested for the tag in the `values` key if there are
saved enumerations for the tag. In the `type` key one of the following values will
appear:

* `common` - The tag values returned are common values but are not the only legal
values for the tag.
* `enumerations` - The tag values returned are the only legal values for the tag.
* `null` - There are no saved enumerations for the tag.

Example: [List of common NMR-STAR versions](http://webapi.bmrb.wisc.edu/v2/enumerations/Entry.NMR_STAR_version)

You can narrow the results to those starting with the value you provide in the
`term` parameter in the query string. This will return the results in a form
that can be used by JQuery's auto-complete.

Example: [List of common NMR-STAR versions starting with 2](http://webapi.bmrb.wisc.edu/v2/enumerations/Entry.NMR_STAR_version?term=2)

#### Instant search (GET)

**/instant?term=$search_term[&database=$database]**

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
archive. [Example link for "john markley mouse"](http://webapi.bmrb.wisc.edu/v2/instant?term=john%20markley%20mouse).
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
Their link points to the "on hold entries" page at BMRB.)
* `authors` - The list of authors for this entry.

If the search matched one of the "additional" search fields (any field other than
ID, Title, Author and Citation) the key `extra` will also exist and point to another
dictionary. That dictionary contains the following two keys:

* `termname` - The name of the field that the search matched. (e.g. organism scientific name)
* `term` - The value of the matching field value from the BMRB entry.

Furthermore, if you perform a query against only the metabolomics database, the
following values will also be returned:

* `average_mass`: The average mass of the compound in daltons. (Natural isotopic
composition.)
* `formula`: The chemical formula.
* `inchi`: The InChI string for the compound.
* `monoisotopic_mass`: Mono-isotopic formula mass calculated using the most
abundant naturally occuring isotope for each atom.
* `smiles`: The canonical SMILES string for the compound.

#### Get assigned chemical shift list (GET)

**/search/chemical_shifts[?database=$database][...]**

Returns all of the chemical shifts in the BMRB for the specified atom type. You
can omit the atom type to fetch all chemical shifts and you can use `*` as a
wild card character. Optionally specify `macromolecule` or `metabolomics` for the
database argument to search a specific database. `macromolecule` is the default.

In addition, the following parameters can be provided using the
[standard notation](https://en.wikipedia.org/wiki/Query_string#Web_forms) to
limit the set of results to those that match the search parameters. All provided
search parameters are combined with a logical AND.

You may use `*` in `atom_id` and `comp_id` as a wildcard to match 0 or more
characters.

* `atom_type` The value for this tag is a standard IUPAC abbreviation for an element (e.g. H,C,P).
* `atom_id` The atom name (e.g. HB2, CB). You may specify this parameter multiple times
and results that match any of the specified atom ids will be returned.
* `comp_id` The residue as a 3 letter code. You may specify this parameter multiple times
and results that match any of the specified residues will be returned.
* `shift` A specific chemical shift to search for. Uses a default threshold of .03.
You may specify this parameter multiple times and results that match any of the
specified chemical shifts will be returned.
* `threshold` Only has meaning in conjunction with `shift`. Specifies the search
threshold for a shift.
* `database` The database to search. Macromolecules or metabolomics.
* `conditions` Set this parameter to any value and two additional columns will be
returned: the pH and the temperature in kelvin associated with the chemical shift.
If those values are not available they will be returned as null.

Examples:

* [All chemical shifts](http://webapi.bmrb.wisc.edu/v2/search/chemical_shifts)
* [All CA chemical shifts](http://webapi.bmrb.wisc.edu/v2/search/chemical_shifts?atom_id=CA)
* [All HB* chemical shifts](http://webapi.bmrb.wisc.edu/v2/search/chemical_shifts?atom_id=HB*)
* [All C1 chemical shifts from metabolomics database](http://webapi.bmrb.wisc.edu/v2/search/chemical_shifts?atom_id=C1&database=metabolomics)
* [All asparagine C chemical shifts within .01 of 175.1 ppm](http://webapi.bmrb.wisc.edu/v2/search/chemical_shifts?atom_id=C&comp_id=ASN&shift=175.1&threshold=.01)
* [All shifts within .03 of 103 or 130 in residue PHE or TRP](http://webapi.bmrb.wisc.edu/v2/search/chemical_shifts?comp_id=TRP&comp_id=PHE&shift=103&shift=130)

#### Search for matching entries based on a lift of shifts (GET)

**/search/multiple_shift_search?shift=x.x[&shift=x.x][...][&database=$database]**

Returns all entries that contain at least one of the queried peaks, as well as
the list of peaks that matched. Results returned as a list of matching entries along
with the matching shifts, number of shifts matched, and total offset of shifts,
sorted by number of peaks matched and total offset. Peaks are counted as a match
if they are within .2 ppm for C and N and if they are within .01 ppm for H.

Parameters:

* `shift` Specify once for each shift you intend to query against.
* `database` Which database to query. Metabolomics by default.

Example: [Search for peaks 2.075, 3.11, and 39.31](http://webapi.bmrb.wisc.edu/v2/search/multiple_shift_search?shift=2.075&shift=3.11&shift=39.31)

#### Get entries with tag matching value (GET)

**/search/get_id_by_tag_value/$tag_name/$tag_value[?database=$database]**

Returns a list of BMRB entry IDs which contain the specified `tag_value` for the
value of at least one instance of tag `tag_name`. The search is done
case-insensitively. You may optionally specify a database if you want
to query the metabolomics database rather than the macromolecule one.

Example: [All entries which used solid-state NMR](http://webapi.bmrb.wisc.edu/v2/search/get_id_by_tag_value/Entry.Experimental_method_subtype/solid-state)

Note that you need the proper tag capitalization for this method. Use
[the dictionary](http://www.bmrb.wisc.edu/dictionary/tag.php) for reference.

#### Get all values for a given tag (GET)

**/search/get_all_values_for_tag/$tag_name[?database=$database]**

Returns a dictionary for the specified dictionary where the keys are entry IDs
and the values are lists of all of the values of the given tag in each entry.
This allows you to get all of the values of a given tag in the BMRB archive for
a given database.

Example: [The citation titles for all entries in the macromolecule database](http://webapi.bmrb.wisc.edu/v2/search/get_all_values_for_tag/Citation.Title)

Example: [The compound names for all compounds in the metabolomics database](http://webapi.bmrb.wisc.edu/v2/search/get_all_values_for_tag/Chem_comp.Name?database=metabolomics)

Note that you need the proper tag capitalization for this method. Use
[the dictionary](http://www.bmrb.wisc.edu/dictionary/tag.php) for reference.

### Software

#### Software summary (GET)

**/software/**

Returns a summary of all software packages used in BMRB entries.

Example: [All software packages used](http://webapi.bmrb.wisc.edu/v2/software/)

#### Software used in an entry (GET)

**/entry/$entry_id/software**

Returns a list of all software packages used by a given entry. Each item in the
list of software will be a list with the following four values in order:

* `software_name` The software package name.
* `software_version` The version of the software package used.
* `software_task` The purpose of the software in this investigation.
* `softare_vender` The software vendor.

[Example for entry 15000](http://webapi.bmrb.wisc.edu/v2/software/entry/15000)

#### Which entries used a given software package (GET)

**/software/package/$software_package/[?database=$database]**

Returns a list of all entries used by the specified software package. The search
is done case-insensitive and does not require perfect matches. For example,
`SPARK` would match `SPARKY` and `NMRFAM_SPARY`.

You may optionally specify which database to use.

Example: [Entries using SPARKY](http://webapi.bmrb.wisc.edu/v2/software/package/sparky?database=macromolecules)

### Molprobity

#### Get one-line molprobity results for a PDB ID (GET)

**/molprobity/$pdb_id/oneline**

Returns the full one-line molprobity results for the given PDB ID.

Example: [PDB 2DOG](http://webapi.bmrb.wisc.edu/v2/molprobity/2dog/oneline)

#### Get residue molprobity results for a PDB ID (GET)

**/molprobity/$pdb_id/residue[?r=$residue][&r=$residue][...]**

Returns the full molprobity residue results for the given PDB ID. You may optionally
specify a list of residues to only get results for those residues.

Parameters:

* `r` Specify the residue to query. May be specified multiple times to get the
results for multiple residues. You cannot use a `-` or `,` to specify residues
at this time.

Example: [PDB 2DOG residues 10,11,12](http://webapi.bmrb.wisc.edu/v2/molprobity/2dog/residue?r=10&r=11&r=12)
