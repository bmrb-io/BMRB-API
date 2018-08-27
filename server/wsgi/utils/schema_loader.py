#!/usr/bin/env python

from __future__ import print_function

import os
import re
import csv
import svn.remote
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


data_type_mapping = [
['Assigned NMR chemical shifts', 'assigned_chemical_shifts', 'Assigned_chem_shifts'],
['Scalar coupling constants', 'coupling_constants', 'Coupling_constants'],  # ???????
['Auto relaxation parameters', 'auto_relaxation', 'Auto_relaxation'],
['Tensor data', 'tensor', 'Tensor'],
['Interatomic distance data', 'interatomic_distance', 'Interatomic_distance'],
['Chemical shift anisotropy', 'chem_shift_anisotropy', 'Chem_shift_anisotropy'],
['Heteronuclear NOEs', 'heteronucl_NOEs', 'Heteronucl_NOEs'],
['T1 (R1) NMR relaxation data', 'heteronucl_T1_relaxation', 'Heteronucl_T1_relaxation'],
['T2 (R2) NMR relaxation data', 'heteronucl_T2_relaxation', 'Heteronucl_T2_relaxation'],
['T1rho (R1rho) NMR relaxation data', 'heteronucl_T1rho_relaxation', 'Heteronucl_T1rho_relaxation'],
['Order parameters', 'order_parameters', 'Order_parameters'],
['Dynamics trajectory file', None, 'Dynamics_trajectory'],
['Dynamics movie file', None, 'Movie'],  # ???
['Residual dipolar couplings', 'RDCs', 'Residual_dipolar_couplings'],
['Hydrogen exchange rates', 'H_exch_rates', 'H_exchange_rate'],
['Hydrogen exchange protection data', 'H_exch_protection_factors', 'H_exchange_protection_factors'],
['Chemical rate constants', 'chemical_rates', 'Chem_rate_constants'],
['Spectral peak lists', 'spectral_peak_list', 'Spectral_peak_lists'],
['Dipole-dipole couplings', None, 'Dipole_dipole_couplings'],
['Quadrupolar couplings', None, 'Quadrupolar_couplings'],
['Homonuclear NOEs', 'homonucl_NOEs', 'Homonucl_NOEs'],
['Dipole-dipole relaxation data', 'dipole_dipole_relaxation', 'Dipole_dipole_relaxation'],
['Dipole-dipole cross correlation data', 'dipole_dipole_cross_correlations', 'DD_cross_correlation'],
['Dipole-CSA cross correlation data', 'dipole_CSA_cross_correlations', 'Dipole_CSA_cross_correlation'],
['Binding constants', 'binding_data', 'Binding_constants'],
['NMR-derived pH transitions (pKa\'s; pHmid\'s)', 'pH_param_list', 'PKa_value_data_set'],
['NMR-derived D/H fractionation factors', 'D_H_fractionation_factors', 'D_H_fractionation_factors'],
['Theoretical (calculated) chemical shift values', 'theoretical_chem_shifts', 'Theoretical_chem_shifts'],
['Spectral density factors', 'spectral_density_values', 'Spectral_density_values'],
['Other kinds of data', 'other_data_types', 'Other_kind_of_data']]


def schema_emitter():
    """ Yields all the schemas in the SVN repo. """

    cur_rev = remote_svn.info()['commit_revision'] + 1

    for rev in range(53, cur_rev):
        yield load_schemas(rev)
    if os.path.exists('nmr-star-dictionary'):
        yield load_schemas('development')


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
                    print("Enumeration for non-existant tag: %s" % saveframe.name)

    except ValueError as e:
        if validate_mode:
            print("Invalid enum file in version %s: %s" % (res['version'], str(e)))
    finally:
        pynmrstar.ALLOW_V2_ENTRIES = False

    res['file_upload_types'] = data_type_mapping

    return res['version'], res
