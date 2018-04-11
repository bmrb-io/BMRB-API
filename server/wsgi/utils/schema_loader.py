#!/usr/bin/env python

import os
import csv
import svn.remote
from querymod import _QUERYMOD_DIR

try:
    # for Python 2.x
    from StringIO import StringIO
except ImportError:
    # for Python 3.x
    from io import StringIO

remote = svn.remote.RemoteClient("http://svn.bmrb.wisc.edu/svn/nmr-star-dictionary")
# Load the data types
dt_path = os.path.join(_QUERYMOD_DIR, "../submodules/PyNMRSTAR/reference_files/data_types.csv")
data_types = {x[0]: x[1] for x in csv.reader(open(dt_path, "rU"))}

validate_mode = False

def schema_emitter():
    """ Yields all the schemas in the SVN repo. """

    cur_rev = remote.info()['commit_revision'] + 1

    for rev in range(53, cur_rev):
        yield load_schemas(remote, rev)

def get_file(file_name, revision):
    """ Returns a file-like object. """

    # Handle old schema location
    schem_loc = "bmrb_only_files/adit_input"
    if revision < 163:
        schem_loc = "bmrb_star_v3_files/adit_input"

    file_ = remote.cat("%s/%s" % (schem_loc, file_name), revision=revision).splitlines()
    file_ = StringIO('\n'.join(file_))
    return file_

def get_main_schema(rev):

    schem = csv.reader(get_file("xlschem_ann.csv", rev))
    all_headers = schem.next()
    schem.next()
    schem.next()
    version = schem.next()[3]

    cc = ['Tag', 'SFCategory', 'BMRB data type', 'Prompt', 'Interface',
          'default value', 'Example', 'User full view',
          'Foreign Table', 'Sf pointer', 'Item enumerated', 'Item enumeration closed']

    header_idx = {x: all_headers.index(x) for x in cc}
    header_idx_list = [all_headers.index(x) for x in cc]
    adit_idx = all_headers.index('ADIT category view name')

    res = {'version': version,
           'tags': {'headers': cc, 'values': {}},
           'saveframes': {'headers': ['ADIT category view name', 'category_group_view_name', 'mandatory_number', 'ADIT replicable', 'group_view_help'],
                          'values': {}}
          }

    for row in schem:
        # First build the saveframe-based information
        saveframe = row[header_idx['SFCategory']]
        if not saveframe in res['saveframes']['values']:
            res['saveframes']['values'][saveframe] = [row[adit_idx].replace("$", ",")]

        # Now build the tag-based information
        res['tags']['values'][row[header_idx['Tag']]] = [row[x].replace("$", ",") for x in header_idx_list]

    return res

def get_dict(fob, headers, skip):
    """ Returns a dictionary with 'key' and 'value' set to point to the
    headers and the values."""

    csv_reader = csv.reader(fob)
    all_headers = csv_reader.next()
    for x in range(0, skip):
        csv_reader.next()

    columns = [all_headers.index(x) for x in headers]
    return {'headers': headers, 'values': [[row[x].replace("$", ",") for x in columns] for row in csv_reader]}

def load_schemas(remote, rev):
    # Load the schemas into the DB

    res = get_main_schema(rev)

    res['data_types'] = data_types
    res['overrides']  = get_dict(get_file("adit_man_over.csv", rev),
                                 ['Tag', 'Sf category', 'Tag category', 'Conditional tag', 'Override view value', 'Override value'],
                                 1)

    # Check for outdated overrides
    if validate_mode:
        for override in res['overrides'] :
            if override[0] != "*" and override[0] not in res['tags']['values']:
                print("Missing tag: %s" % override[0])

    sf_category_info = get_dict(get_file("adit_cat_grp_i.csv", rev),
                                ['saveframe_category', 'category_group_view_name', 'mandatory_number', 'ADIT replicable', 'group_view_help'],
                                2)
    for sfo in sf_category_info['values']:
        try:
            res['saveframes']['values'][sfo[0]].extend(sfo[1:])
        except KeyError:
            if validate_mode:
                print("SF category in adit_cat_grp but not xlschem_ann: %s" % sfo[0])
            else:
                pass

    #res)
    return res['version'], res

