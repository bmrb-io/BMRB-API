## BMRB Entry JSON format

To convert from NMR-STAR to JSON format the minimal amount of data needed to
reconstruct a BMRB entry is converted to dictionaries and lists in JSON format
in a hierarchical approach that attempts to mimic that which exists in the
NMR-STAR format. If you are using the
[PyNMR-STAR python library](https://github.com/uwbmrb/PyNMRSTAR) that we have
released there are fromJSON() and toJSON() methods available for entries,
saveframes, and loops that allow you to convert into and read from JSON format.

[This page](http://www.jsoneditoronline.org/?url=http://webapi.bmrb.wisc.edu/current/rest/entry/15000/)
will allow you to view a full entry interactively.

If you need a reminder on the format of NMR-STAR - which the JSON is created
from - please see the
[NMR-STAR viewer page](http://www.bmrb.wisc.edu/dictionary/starviewer/?entry=15000)
for the same entry. As an aside, the STAR-viewer page linked here is using the
API to load the data which it displays in NMR-STAR format.

### Entry

Here is the structure of one entry in JSON format:

```json
{
    "bmrb_id": "bmrb_id",
    "saveframes": ["..."]
}
```

The `...` above contains all of the entry's saveframes in JSON format:

### Saveframe

```json
{
    "category": "saveframe_category",
    "tag_prefix": "_Entry",
    "name": "saveframe_name",
    "tags": [["tag1", "value1"], ["tag2", "value2"], ["etc.", "etc."]],
    "loops": ["..."]
}
```

Again - the `...` above contains the saveframes' loops in JSON format:

### Loop

```json
{
    "category": "_Entry_author",
    "tags": ["tag1", "tag2", "etc."],
    "data": [
        ["row", 1, "data"],
        ["row", 2, "data"],
        ["etc", 3, "data"]
    ]
}
```

Note that "tags" key corresponds to the column names in the loop.

### Example entry

Here is an example of entry 15000 in JSON format, but with all but the first
saveframe removed.

```json
{
    "bmrb_id": "15000",
    "saveframes": [
    {
        "category": "entry_information",
        "tag_prefix": "_Entry",
        "name": "entry_information",
        "tags": [
            ["Sf_category", "entry_information"],
            ["Sf_framecode", "entry_information"],
            ["ID", "15000" ],
            ["Title", "Solution structure of chicken villin headpiece subdomain containing a fluorinated side chain in the core\n"],
            ["Type", "macromolecule"],
            ["Version_type", "original"],
            ["Submission_date", "2006-09-07"],
            ["Accession_date", "2006-09-07"],
            ["Last_release_date", "."],
            ["Original_release_date", "."],
            ["Origination", "author"],
            ["NMR_STAR_version", "3.1.1.61"],
            ["Original_NMR_STAR_version", "."],
            ["Experimental_method", "NMR"],
            ["Experimental_method_subtype", "solution"],
            ["Details", "."],
            ["BMRB_internal_directory_name", "."]
        ],
        "loops": [
            {
                "category": "_Entry_author",
                "data": [
                  ["1", "Claudia", "Cornilescu", ".", "C.", ".", "15000"],
                  ["2", "Gabriel", "Cornilescu", ".", ".", ".", "15000"],
                  ["3", "Erik", "Hadley", ".", "B.", ".", "15000"],
                  ["4", "Samuel", "Gellman", ".", "H.", ".", "15000"],
                  ["5", "John", "Markley", ".", "L.", ".", "15000"]
                ],
                "tags": ["Ordinal", "Given_name", "Family_name", "First_initial", "Middle_initials", "Family_title", "Entry_ID"]
              },
              {
                "category": "_SG_project",
                "data": [
                  ["1", "not applicable", "not applicable", ".", "15000"]
                ],
                "tags": ["SG_project_ID", "Project_name", "Full_name_of_center", "Initial_of_center", "Entry_ID"]
              },
              {
                "category": "_Struct_keywords",
                "data": [
                  ["chicken villin headpiece", ".", "15000"],
                  ["fluorinated Phe", ".", "15000"],
                  ["VHP", ".", "15000"]
                ],
                "tags": ["Keywords", "Text", "Entry_ID"]
              },
              {
                "category": "_Data_set",
                "data": [
                  ["assigned_chemical_shifts", "1", "15000"]
                ],
                "tags": ["Type", "Count", "Entry_ID"]
              },
              {
                "category": "_Datum",
                "data": [
                  ["13C chemical shifts", "77", "15000" ],
                  ["15N chemical shifts", "40", "15000"],
                  ["1H chemical shifts", "223", "15000"]
                ],
                "tags": ["Type", "Count", "Entry_ID"]
              },
              {
                "category": "_Release",
                "data": [
                  ["2", ".", ".", "2008-07-17", "2006-09-06", "update", "BMRB", "complete entry citation", "15000"],
                  ["1", ".", ".", "2006-10-20", "2006-09-06", "original", "author", "original release", "15000"]
                ],
                "tags": ["Release_number", "Format_type", "Format_version", "Date", "Submission_date", "Type", "Author", "Detail", "Entry_ID"]
              },
              {
                "category": "_Related_entries",
                "data": [
                    ["PDB", "2JM0", "BMRB Entry Tracking System", "15000"]
                ],
                "tags": ["Database_name", "Database_accession_code", "Relationship", "Entry_ID"]
              }
        ]
        },
        "More saveframes would go here..."
    ]
}
```
