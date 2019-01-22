#!/usr/bin/env python

from __future__ import print_function

import os
import re
import csv
import svn.remote
from svn.exception import SvnException
from querymod import _QUERYMOD_DIR, pynmrstar

try:
    # for Python 2.x
    from StringIO import StringIO
except ImportError:
    # for Python 3.x
    from io import StringIO

remote_svn = svn.remote.RemoteClient("http://svn.bmrb.wisc.edu/svn/nmr-star-dictionary")
# Load the data types
dt_path = os.path.join(_QUERYMOD_DIR, "../submodules/PyNMRSTAR/reference_files/data_types.csv")
data_types = {x[0]: x[1] for x in csv.reader(open(dt_path, "rU"))}

validate_mode = False

data_type_mapping = {'Assigned_chem_shifts': 'assigned_chemical_shifts',
                     'Coupling_constants': 'coupling_constants',
                     'Auto_relaxation': 'auto_relaxation',
                     'Interatomic_distance': 'interatomic_distance',
                     'Chem_shift_anisotropy': 'chem_shift_anisotropy',
                     'Heteronucl_NOEs': 'heteronucl_NOEs',
                     'Heteronucl_T1_relaxation': 'heteronucl_T1_relaxation',
                     'Heteronucl_T2_relaxation': 'heteronucl_T2_relaxation',
                     'Heteronucl_T1rho_relaxation': 'heteronucl_T1rho_relaxation',
                     'Order_parameters': 'order_parameters',
                     'Dynamics_trajectory': None,
                     'Movie': None,
                     'Residual_dipolar_couplings': 'RDCs',
                     'H_exchange_rate': 'H_exch_rates',
                     'H_exchange_protection_factors': 'H_exch_protection_factors',
                     'Chem_rate_constants': 'chemical_rates',
                     'Spectral_peak_lists': 'spectral_peak_list',
                     'Dipole_dipole_couplings': None,
                     'Quadrupolar_couplings': None,
                     'Homonucl_NOEs': 'homonucl_NOEs',
                     'Dipole_dipole_relaxation': 'dipole_dipole_relaxation',
                     'DD_cross_correlation': 'dipole_dipole_cross_correations',
                     'Dipole_CSA_cross_correlation': 'dipole_CSA_cross_correlations',
                     'Binding_constants': 'binding_data',
                     'PKa_value_data_set': 'pH_param_list',
                     'D_H_fractionation_factors': 'D_H_fractionation_factors',
                     'Theoretical_chem_shifts': 'theoretical_chem_shifts',
                     'Spectral_density_values': 'spectral_density_values',
                     'Other_kind_of_data': 'other_data_types',
                     'Theoretical_coupling_constants': 'theoretical_coupling_constants',
                     'Theoretical_heteronucl_NOEs': 'theoretical_heteronucl_NOEs',
                     'Theoretical_T1_relaxation': 'theoretical_heteronucl_T1_relaxation',
                     'Theoretical_T2_relaxation': 'theoretical_heteronucl_T2_relaxation',
                     'Theoretical_auto_relaxation': 'theoretical_auto_relaxation',
                     'Theoretical_DD_cross_correlation': 'theoretical_dipole_dipole_cross_correlations',
                     'Timedomain_data': None,
                     'Molecular_interactions': None,
                     'Secondary_structure_orientations': 'secondary_structs',
                     'Metabolite_coordinates': None,
                     'Tensor': None,
                     'Mass_spec_data': None,
                     'Chem_shift_perturbation': 'chem_shift_perturbation',
                     'Chem_shift_isotope_effect': 'chem_shift_isotope_effect',
                     'Image_file': 'chem_comp'
                     }


def schema_emitter():
    """ Yields all the schemas in the SVN repo. """

    cur_rev = remote_svn.info()['commit_revision']
    last_schema_version = None

    if os.path.exists('nmr-star-dictionary'):
        next_schema = load_schemas('development')
        last_schema_version = next_schema[0]
        yield next_schema

    for rev in range(cur_rev, 52, -1):
        next_schema = load_schemas(rev)
        if next_schema[0] != last_schema_version:
            yield next_schema
        last_schema_version = next_schema[0]


def get_file(file_name, revision):
    """ Returns a file-like object. """

    # Handle old schema location
    schema_loc = "bmrb_only_files/adit_input"
    if revision < 163:
        schema_loc = "bmrb_star_v3_files/adit_input"

    if revision == "development":
        file_ = open('nmr-star-dictionary/bmrb_only_files/adit_input/%s' % file_name, 'r').read().splitlines()
    else:
        file_ = remote_svn.cat("%s/%s" % (schema_loc, file_name), revision=revision).splitlines()
    file_ = StringIO('\n'.join(file_))
    return file_


def get_main_schema(rev):
    schema = csv.reader(get_file("xlschem_ann.csv", rev))
    all_headers = schema.next()
    schema.next()
    schema.next()
    version = schema.next()[3]

    cc = ['Tag', 'Tag category', 'SFCategory', 'BMRB data type', 'Prompt', 'Interface',
          'default value', 'Example', 'User full view',
          'Foreign Table', 'Sf pointer', 'Item enumerated', 'Item enumeration closed', 'ADIT category view name',
          'Enumeration ties']
    # Todo: remove ADIT category view name once code is refactored

    header_idx = {x: all_headers.index(x) for x in cc}
    header_idx_list = [all_headers.index(x) for x in cc]

    res = {'version': version,
           'tags': {'headers': cc + ['enumerations'], 'values': {}},
           }

    for row in schema:
        res['tags']['values'][row[header_idx['Tag']]] = [row[x].replace("$", ",") for x in header_idx_list]

    return res


def get_data_file_types(rev):
    """ Returns the list of enabled data file [description, sf_category, entry_interview.tag_name. """

    try:
        enabled_types_file = csv.reader(get_file("adit_nmr_upload_tags.csv", rev))
    except SvnException:
        return

    pynmrstar.ALLOW_V2_ENTRIES = True
    types_description = pynmrstar.Entry.from_file(get_file('adit_interface_dict.txt', rev))

    for data_type in enabled_types_file:
        try:
            sf = types_description[data_type[1]]
            type_description = sf['_Adit_item_view_name'][0].strip()
            interview_tag = pynmrstar._format_tag(sf['_Tag'][0])
            # Try to get the data mapping from the dictionary if possible
            if len(data_type) > 2:
                if data_type[2] == "?":
                    sf_category = None
                else:
                    sf_category = data_type[2]
            else:
                sf_category = data_type_mapping.get(interview_tag, None)
            description = sf['_Description'][0]
            yield [type_description, sf_category, interview_tag, description]
        except Exception as e:
            print('Something went wrong when loading the data types mapping.', repr(e))
            return


def get_dict(fob, headers, number_fields, skip):
    """ Returns a dictionary with 'key' and 'value' set to point to the
    headers and the values."""

    csv_reader = csv.reader(fob)
    all_headers = csv_reader.next()
    for x in range(0, skip):
        csv_reader.next()

    def skip_end():
        for csv_row in csv_reader:
            if csv_row[0] != "TBL_END" and csv_row[0]:
                yield csv_row

    columns = [all_headers.index(x) for x in headers]
    values = [[row[x].replace("$", ",") for x in columns] for row in skip_end()]

    number_fields = [headers.index(x) for x in number_fields]
    for row in values:
        for i in number_fields:
            try:
                if row[i]:
                    row[i] = int(row[i])
                else:
                    row[i] = 0
            except ValueError:
                print(row)

    return {'headers': headers, 'values': values}


def load_schemas(rev):
    # Load the schemas into the DB

    res = get_main_schema(rev)

    res['data_types'] = data_types
    res['overrides'] = get_dict(get_file("adit_man_over.csv", rev),
                                ['Tag', 'Sf category', 'Tag category', 'Conditional tag', 'Override view value',
                                 'Override value', 'Order of operation'],
                                ['Order of operation'],
                                1)

    res['supergroup_descriptions'] = get_dict(get_file('adit_super_grp_o.csv', rev),
                                              ['super_group_ID', 'super_group_name', 'Description'],
                                              ['super_group_ID'],
                                              2)

    res['category_supergroups'] = get_dict(get_file("adit_cat_grp_o.csv", rev),
                                           ['category_super_group', 'saveframe_category', 'mandatory_number',
                                            'allowed_user_defined_framecode', 'category_group_view_name',
                                            'group_view_help', 'category_super_group_ID'],
                                           ['mandatory_number', 'category_super_group_ID'],
                                           2)

    # Check for outdated overrides
    if validate_mode:
        for override in res['overrides']:
            if override[0] != "*" and override[0] not in res['tags']['values']:
                print("Missing tag: %s" % override[0])

    sf_category_info = get_dict(get_file("adit_cat_grp_i.csv", rev),
                                ['saveframe_category', 'category_group_view_name', 'mandatory_number',
                                 'ADIT replicable', 'group_view_help'],
                                ['mandatory_number'],
                                2)

    res['saveframes'] = {'headers': sf_category_info['headers'][1:], 'values': {}}
    for sfo in sf_category_info['values']:
        res['saveframes']['values'][sfo[0]] = sfo[1:]

    # Load the enumerations
    try:
        enumerations = get_file('enumerations.txt', rev).read()
        enumerations = re.sub('_Revision_date.*', '', enumerations.replace('\x00', '').replace('\xd5', ''))
        pynmrstar.ALLOW_V2_ENTRIES = True
        enum_entry = pynmrstar.Entry.from_string(enumerations)
        for saveframe in enum_entry:
            enums = [x.replace("$", ",") for x in saveframe[0].get_data_by_tag('_item_enumeration_value')[0]]
            try:
                res['tags']['values'][saveframe.name].append(enums)
            except KeyError:
                if validate_mode:
                    print("Enumeration for non-existent tag: %s" % saveframe.name)

    except ValueError as e:
        if validate_mode:
            print("Invalid enum file in version %s: %s" % (res['version'], str(e)))
    finally:
        pynmrstar.ALLOW_V2_ENTRIES = False

    res['file_upload_types'] = list(get_data_file_types(rev))

    return res['version'], res
