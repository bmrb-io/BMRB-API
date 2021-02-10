import csv
import os
import subprocess
import tempfile
import zlib
from decimal import Decimal
from hashlib import md5
from io import StringIO
from time import time as unix_time
from typing import List, Dict

import pynmrstar
from flask import Blueprint, Response, request, jsonify, send_file, make_response
from pybmrb import csviz

from bmrbapi.exceptions import ServerException, RequestException
from bmrbapi.utils import querymod
from bmrbapi.utils.configuration import configuration
from bmrbapi.utils.connections import PostgresConnection, RedisConnection
from bmrbapi.utils.mappings import three_letter_code_to_one
from bmrbapi.utils.querymod import get_valid_entries_from_redis

entry_endpoints = Blueprint('entry', __name__)


# Helper functions defined before the views
def check_valid(entry_id) -> None:
    """ Checks if a given entry ID exists in redis. If not, throws a RequestException."""

    with RedisConnection() as r:
        if not r.exists(querymod.locate_entry(entry_id, r_conn=r)):
            raise RequestException("Entry '%s' does not exist in the public database." % entry_id, status_code=404)


def get_tags(entry_id: str, search_tags: List[str]) -> Dict[str, Dict[str, List[str]]]:
    """ Returns results for the queried tags."""

    # Check the validity of the tags
    for tag in search_tags:
        if "." not in tag:
            raise RequestException("You must provide the tag category to call this method at the entry level. For "
                                   "example, use 'Entry.Title' rather than 'Title'.")

    # Go through the IDs
    entry = next(get_valid_entries_from_redis(entry_id))
    try:
        return {entry[0]: entry[1].get_tags(search_tags)}
    # They requested a tag that doesn't exist
    except ValueError as error:
        raise RequestException(str(error))


def get_loops_by_category(entry_id: str, loop_categories: List[str], format_: str) -> \
        Dict[str, Dict[str, List[pynmrstar.Loop]]]:
    """ Returns the matching loops."""

    result = {}

    # Go through the IDs
    for entry in get_valid_entries_from_redis(entry_id):
        result[entry[0]] = {}
        for loop_category in loop_categories:
            matches = entry[1].get_loops_by_category(loop_category)

            if format_ == "rawnmrstar":
                response = make_response("\n".join([str(x) for x in matches]), 200)
                response.mimetype = "text/plain"
                return response
            else:
                matching_loops = [x.get_json(serialize=False) for x in matches]
            result[entry[0]][loop_category] = matching_loops

    return jsonify(result)


def get_saveframes_by_category(entry_id: str, saveframe_categories: List[str], format_: str) -> \
        Dict[str, Dict[str, List[pynmrstar.Saveframe]]]:
    """ Returns the matching saveframes."""

    result = {}

    # Go through the IDs
    entry = next(get_valid_entries_from_redis(entry_id))
    result[entry[0]] = {}
    for saveframe_category in saveframe_categories:
        matches = entry[1].get_saveframes_by_category(saveframe_category)
        if format_ == "rawnmrstar":
            response = make_response("\n".join([str(x) for x in matches]), 200)
            response.mimetype = "text/plain"
            return response
        else:
            matching_frames = [x.get_json(serialize=False) for x in matches]
        result[entry[0]][saveframe_category] = matching_frames
    return jsonify(result)


def get_saveframes_by_name(entry_id: str, saveframe_names: List[str], format_: str) -> \
        Dict[str, Dict[str, List[pynmrstar.Saveframe]]]:
    """ Returns the matching saveframes."""

    result = {}

    # Go through the IDs
    entry = next(get_valid_entries_from_redis(entry_id))
    result[entry[0]] = {}
    for saveframe_name in saveframe_names:
        try:
            sf = entry[1].get_saveframe_by_name(saveframe_name)
            if format_ == "rawnmrstar":
                response = make_response(str(sf), 200)
                response.mimetype = "text/plain"
                return response
            else:
                result[entry[0]][saveframe_name] = sf.get_json(serialize=False)
        except KeyError:
            continue

    return jsonify(result)


def panav_parser(panav_text: bytes) -> dict:
    """ Parses the PANAV data into something jsonify-able."""

    panav_text: str = panav_text.decode()

    lines = panav_text.split("\n")

    # Initialize the result dictionary
    result = {'offsets': {}, 'deviants': [], 'suspicious': [], 'text': panav_text}

    # Variables to keep track of output line numbers
    deviant_line = 5
    suspicious_line = 6

    # There is an error
    if len(lines) < 3:
        raise ServerException("PANAV failed to produce expected output. Output: %s" % panav_text)

    # Check for unusual output
    if "No reference" in lines[0]:
        # Handle the special case when no offsets
        result['offsets'] = {'CO': float(0), 'CA': float(0), 'CB': float(0), 'N': float(0)}
        deviant_line = 1
        suspicious_line = 2
    # Normal output
    else:
        result['offsets']['CO'] = float(lines[1].split(" ")[-1].replace("ppm", ""))
        result['offsets']['CA'] = float(lines[2].split(" ")[-1].replace("ppm", ""))
        result['offsets']['CB'] = float(lines[3].split(" ")[-1].replace("ppm", ""))
        result['offsets']['N'] = float(lines[4].split(" ")[-1].replace("ppm", ""))

    # Figure out how many deviant and suspicious shifts were detected
    num_deviants = int(lines[deviant_line].rstrip().split(" ")[-1])
    num_suspicious = int(lines[suspicious_line + num_deviants].rstrip().split(" ")[-1])
    suspicious_line += num_deviants + 1
    deviant_line += 1

    # Get the deviants
    for deviant in lines[deviant_line:deviant_line + num_deviants]:
        res_num, res, atom, shift = deviant.strip().split(" ")
        result['deviants'].append({"residue_number": res_num, "residue_name": res,
                                   "atom": atom, "chemical_shift_value": shift})

    # Get the suspicious shifts
    for suspicious in lines[suspicious_line:suspicious_line + num_suspicious]:
        res_num, res, atom, shift = suspicious.strip().split(" ")
        result['suspicious'].append({"residue_number": res_num, "residue_name": res,
                                     "atom": atom, "chemical_shift_value": shift})

    # Return the result dictionary
    return result


@entry_endpoints.route('/entry', methods=['POST'])
@entry_endpoints.route('/entry/<entry_id>', methods=['GET'])
def get_entry(entry_id=None):
    """ Returns an entry in the specified format."""

    # Get the format they want the results in
    format_ = request.args.get('format', "json")

    # If they are storing
    if request.method == "POST":
        uploaded_data = request.data

        if not uploaded_data:
            raise RequestException("No data uploaded. Please post the NMR-STAR file as the request body.")

        if request.content_type == "application/json":
            try:
                parsed_star = pynmrstar.Entry.from_json(uploaded_data.decode())
            except (ValueError, TypeError) as e:
                raise RequestException("Invalid uploaded JSON NMR-STAR data. Exception: %s" % e)
        else:
            try:
                parsed_star = pynmrstar.Entry.from_string(uploaded_data.decode())
            except ValueError as e:
                raise RequestException("Invalid uploaded NMR-STAR file. Exception: %s" % e)

        key = md5(uploaded_data).hexdigest()

        with RedisConnection() as r:
            r.setex("uploaded:entry:%s" % key, configuration['redis']['upload_timeout'],
                    zlib.compress(parsed_star.get_json(serialize=True).encode()))

        return jsonify({"entry_id": key, "expiration": unix_time() + configuration['redis']['upload_timeout']})

    # Loading
    else:
        # Make sure it is a valid entry
        check_valid(entry_id)

        # See if they specified more than one of [saveframe, loop, tag]
        args = sum([1 if request.args.get('saveframe_category', None) else 0,
                    1 if request.args.get('saveframe_name', None) else 0,
                    1 if request.args.get('loop', None) else 0,
                    1 if request.args.get('tag', None) else 0])
        if args > 1:
            raise RequestException("Request either loop(s), saveframe(s) by category, saveframe(s) by name, "
                                   "or tag(s) but not more than one simultaneously.")

        # See if they are requesting one or more saveframe
        elif request.args.get('saveframe_category', None):
            return get_saveframes_by_category(entry_id, request.args.getlist('saveframe_category'), format_)

        # See if they are requesting one or more saveframe
        elif request.args.get('saveframe_name', None):
            return get_saveframes_by_name(entry_id, request.args.getlist('saveframe_name'), format_)

        # See if they are requesting one or more loop
        elif request.args.get('loop', None):
            return get_loops_by_category(entry_id, request.args.getlist('loop'), format_)

        # See if they want a tag
        elif request.args.get('tag', None):
            return jsonify(get_tags(entry_id, request.args.getlist('tag')))

        # They want an entry
        else:
            # Get the entry
            entry_id, entry = next(querymod.get_valid_entries_from_redis(entry_id, format_=format_))

            # Bypass JSON encode/decode cycle
            if format_ == "json":
                return Response("""{"%s": %s}""" % (entry_id, entry.decode()), mimetype="application/json")

            # Special case to return raw nmrstar
            elif format_ == "rawnmrstar":
                return Response(entry, mimetype="text/plain")

            # Special case for raw zlib
            elif format_ == "zlib":
                return Response(entry, mimetype="application/zlib")

            # Return the entry in any other format
            return jsonify(entry)


@entry_endpoints.route('/entry/<entry_id>/software')
def get_software_by_entry(entry_id):
    """ Returns the software used on a per-entry basis. """

    if not entry_id:
        raise RequestException("You must specify the entry ID.")

    with PostgresConnection(schema=querymod.get_database_from_entry_id(entry_id)) as cur:
        cur.execute('''
SELECT "Software"."Name", "Software"."Version", task."Task" AS "Task", vendor."Name" AS "Vendor Name"
FROM "Software"
         LEFT JOIN "Vendor" AS vendor
                   ON "Software"."Entry_ID" = vendor."Entry_ID" AND "Software"."ID" = vendor."Software_ID"
         LEFT JOIN "Task" AS task ON "Software"."Entry_ID" = task."Entry_ID" AND "Software"."ID" = task."Software_ID"
WHERE "Software"."Entry_ID" = %s''', [entry_id])

        column_names = [desc[0] for desc in cur.description]
        results = cur.fetchall()

        # If no results, make sure the entry exists
        if len(results) == 0:
            check_valid(entry_id)

        return jsonify({"columns": column_names, "data": results})


@entry_endpoints.route('/entry/<entry_id>/experiments')
def get_experiment_data(entry_id):
    """ Return the experiments available for an entry. """

    # First get the sample components
    with PostgresConnection(schema=querymod.get_database_from_entry_id(entry_id)) as cur:
        sql = '''
SELECT "Mol_common_name", "Isotopic_labeling", "Type", "Concentration_val", "Concentration_val_units", "Sample_ID"
FROM "Sample_component"
WHERE "Entry_ID" = %s'''
        cur.execute(sql, [entry_id])
        stored_results = cur.fetchall()

        # Then get all of the other information
        sql = '''
SELECT me."Entry_ID",
       me."Sample_ID",
       me."ID",
       ns."Manufacturer",
       ns."Model",
       me."Name"                      AS experiment_name,
       ns."Field_strength",
       array_agg(ef."Name")           AS name,
       array_agg(ef."Type")           AS type,
       array_agg(ef."Directory_path") AS directory_path,
       array_agg(ef."Details")        AS details,
       ph."Val"                       AS ph,
       temp."Val"                     AS temp
FROM "Experiment" AS me
         LEFT JOIN "Experiment_file" AS ef
                   ON me."ID" = ef."Experiment_ID" AND me."Entry_ID" = ef."Entry_ID"
         LEFT JOIN "NMR_spectrometer" AS ns
                   ON ns."Entry_ID" = me."Entry_ID" AND ns."ID" = me."NMR_spectrometer_ID"

         LEFT JOIN "Sample_condition_variable" AS ph
                   ON me."Sample_condition_list_ID" = ph."Sample_condition_list_ID" AND
                      ph."Entry_ID" = me."Entry_ID" AND ph."Type" = 'pH'
         LEFT JOIN "Sample_condition_variable" AS temp
                   ON me."Sample_condition_list_ID" = temp."Sample_condition_list_ID" AND
                      temp."Entry_ID" = me."Entry_ID" AND
                      temp."Type" = 'temperature' AND temp."Val_units" = 'K'

WHERE me."Entry_ID" = %s
GROUP BY me."Entry_ID", me."Name", me."ID", ns."Manufacturer", ns."Model", ns."Field_strength", ph."Val",
         temp."Val", me."Sample_ID"
ORDER BY me."Entry_ID", me."ID";'''
        cur.execute(sql, [entry_id])
        all_results = cur.fetchall()

    results = []
    for row in all_results:

        data = []
        if row['name'][0]:
            for x, item in enumerate(row['directory_path']):
                data.append({'type': row['type'][x], 'description': row['details'][x],
                             'url': "https://bmrb.io/ftp/pub/bmrb/metabolomics/entry_directories/%s/%s/%s" % (
                                 row['Entry_ID'], row['directory_path'][x], row['name'][x])})

        tmp_res = {'Name': row['experiment_name'],
                   'Experiment_ID': row['ID'],
                   'Sample_condition_variable': {'ph': row['ph'],
                                                 'temperature': row['temp']},
                   'NMR_spectrometer': {'Manufacturer': row['Manufacturer'],
                                        'Model': row['Model'],
                                        'Field_strength': row['Field_strength']
                                        },
                   'Experiment_file': data,
                   'Sample_component': []}
        for component in stored_results:
            if component['Sample_ID'] == row['Sample_ID']:
                smp = {'Mol_common_name': component['Mol_common_name'],
                       'Isotopic_labeling': component['Isotopic_labeling'],
                       'Type': component['Type'],
                       'Concentration_val': component['Concentration_val'],
                       'Concentration_val_units': component['Concentration_val_units']}
                tmp_res['Sample_component'].append(smp)

        results.append(tmp_res)
    # If no results, make sure the entry exists
    if len(results) == 0:
        check_valid(entry_id)
    return jsonify(results)


@entry_endpoints.route('/entry/<entry_id>/citation')
def get_citation(entry_id):
    """ Return the citation information for an entry in the requested format. """

    format_ = request.args.get('format', "json-ld")

    # Error if invalid
    if format_ not in ["json-ld", "text", "bibtex"]:
        raise RequestException("Invalid format specified. Please choose from the following formats: %s" %
                               str(["json-ld", "text", "bibtex"]))

    try:
        ent_ret_id, entry = next(get_valid_entries_from_redis(entry_id))
    except StopIteration:
        raise RequestException("Entry '%s' does not exist in the public database." % entry_id)

    # First lets get all the values we need, later we will format them

    def get_tag(saveframe, tag):
        tag = saveframe.get_tag(tag)
        if not tag:
            return ""
        else:
            return tag[0]

    # Authors and citations
    authors = []
    citations = []
    citation_title, citation_journal, citation_volume_issue, citation_pagination, citation_year = '', '', '', '', ''

    for citation_frame in entry.get_saveframes_by_category("citations"):
        if get_tag(citation_frame, "Class") == "entry citation":
            cl = citation_frame["_Citation_author"]

            # Get the journal information
            citation_journal = get_tag(citation_frame, "Journal_abbrev")
            issue = get_tag(citation_frame, "Journal_issue")
            if issue and issue != ".":
                issue = "(%s)" % issue
            else:
                issue = ""
            volume = get_tag(citation_frame, "Journal_volume")
            if not volume or volume == ".":
                volume = ""
            citation_volume_issue = "%s%s" % (volume, issue)
            citation_year = get_tag(citation_frame, "Year")
            citation_pagination = "%s-%s" % (get_tag(citation_frame, "Page_first"),
                                             get_tag(citation_frame, "Page_last"))
            citation_title = get_tag(citation_frame, "Title").strip()

            # Authors
            for row in cl.get_tag(["Given_name", "Family_name", "Middle_initials"]):
                auth = {"@type": "Person", "givenName": row[0], "familyName": row[1]}
                if row[2] != ".":
                    auth["additionalName"] = row[2]
                authors.append(auth)

            # Citations
            doi = get_tag(citation_frame, "DOI")
            if doi and doi != ".":
                citations.append({"@type": "ScholarlyArticle",
                                  "@id": "https://doi.org/" + doi,
                                  "headline": get_tag(citation_frame, "Title"),
                                  "datePublished": get_tag(citation_frame, "Year")})

    # Figure out last update day, version, and original release
    orig_release, last_update, version = None, None, 1
    for row in entry.get_loops_by_category("Release")[0].get_tag(["Release_number", "Date"]):
        if row[0] == "1":
            orig_release = row[1]
        if int(row[0]) >= version:
            last_update = row[1]
            version = int(row[0])

    # Title
    title = entry.get_tag("Entry.Title")[0].rstrip()

    # DOI string
    doi = "10.13018/BMR%s" % ent_ret_id
    if ent_ret_id.startswith("bmse") or ent_ret_id.startswith("bmst"):
        doi = "10.13018/%s" % ent_ret_id.upper()

    if format_ == "json-ld":
        res = {"@context": "http://schema.org",
               "@type": "Dataset",
               "@id": "https://doi.org/10.13018/%s" % doi,
               "publisher": "Biological Magnetic Resonance Bank",
               "datePublished": orig_release,
               "dateModified": last_update,
               "version": "v%s" % version,
               "name": title,
               "author": authors}

        if len(citations) > 0:
            res["citation"] = citations

        return jsonify(res)

    elif format_ == "bibtex":
        ret_string = """@misc{%(entry_id)s,
 author = {%(author)s},
 publisher = {Biological Magnetic Resonance Bank},
 title = {%(title)s},
 year = {%(year)s},
 month = {%(month)s},
 doi = {%(doi)s},
 howpublished = {https://doi.org/%(doi)s}
 url = {https://doi.org/%(doi)s}
}"""

        ret_keys = {"entry_id": ent_ret_id, "title": title,
                    "year": orig_release[0:4], "month": orig_release[5:7],
                    "doi": doi,
                    "author": " and ".join([x["familyName"] + ", " + x["givenName"] for x in authors])}

        return Response(ret_string % ret_keys, mimetype="application/x-bibtex",
                        headers={"Content-disposition": "attachment; filename=%s.bib" % entry_id})

    elif format_ == "text":

        names = []
        for x in authors:
            name = x["familyName"] + ", " + x["givenName"][0] + "."
            if "additionalName" in x:
                name += x["additionalName"]
            names.append(name)

        text_dict = {"entry_id": entry_id, "title": title,
                     "citation_title": citation_title,
                     "citation_journal": citation_journal,
                     "citation_volume_issue": citation_volume_issue,
                     "citation_pagination": citation_pagination,
                     "citation_year": citation_year,
                     "author": ", ".join(names),
                     "doi": doi}

        if citation_journal:
            citation = """BMRB ID: %(entry_id)s
%(author)s
%(citation_title)s
%(citation_journal)s %(citation_volume_issue)s pp. %(citation_pagination)s (%(citation_year)s) doi: %(doi)s""" % \
                       text_dict
        else:
            citation = "BMRB ID: %(entry_id)s %(author)s %(title)s doi: %(doi)s" % text_dict

        return Response(citation, mimetype="text/plain")


@entry_endpoints.route('/entry/<entry_id>/simulate_hsqc')
def simulate_hsqc(entry_id):
    """ Returns the html for a simulated HSQC spectrum. """

    format_ = request.args.get('format', "html")
    filter_ = request.args.get('filter', "all")

    # The PyBMRB exception only fires if the entry ID is valid
    check_valid(entry_id)

    if format_ == 'html':
        csviz._AUTOOPEN = False
        csviz._OPACITY = 1
        with tempfile.NamedTemporaryFile(suffix='.html') as output_file:
            try:
                csviz.Spectra().n15hsqc(entry_id, outfilename=output_file.name)
            except ValueError:
                return 'No amide proton nitrogen chemical shifts found.'
            output_file.seek(0)
            if len(output_file.read()) == 0:
                raise ServerException('PyBMRB failed to generate valid output.')
            return send_file(output_file.name)
    elif format_ in ['csv', 'json', 'sparky']:
        spectra = csviz.Spectra()
        cs_data = spectra.get_entry(entry_id)
        data = list(zip(*spectra.convert_to_n15hsqc_peaks(cs_data)))
        dict_format = [{'sequence': int(_[0].split("-")[1]),
                        'chem_comp_ID': _[0].split("-")[2],
                        'H_shift': Decimal(_[1]),
                        'N_shift': Decimal(_[2]),
                        'H_atom_name': _[3],
                        'N_atom_name': _[4]} for _ in data if
                       ((filter_ == 'all' or (_[3] == 'H' and _[4] == 'N')) and _[1] and _[2])]

        if format_ == 'json':
            return jsonify(dict_format)
        elif format_ == 'sparky':
            sparky_file = "Assignment         w1        w2\n\n"
            for row in dict_format:
                if row['H_shift'] and row['N_shift']:
                    assignment = f'{three_letter_code_to_one.get(row["chem_comp_ID"],"X")}{row["sequence"]}' \
                                 f'{row["H_atom_name"]}-{row["N_atom_name"]}'
                    if filter_ == "all" or (row['H_atom_name'] == 'H' and row['N_atom_name'] == 'N'):
                        sparky_file += f'{assignment:12} {row["H_shift"]:8} {row["N_shift"]:8}\n'

            response = Response(sparky_file, mimetype='text/plain')
            response.headers.set("Content-Disposition", 'attachment',
                                 filename=f'{entry_id}_simulated_hsqc_{filter_}.list')
            return response

        elif format_ == 'csv':
            memory_file = StringIO()
            csv_writer = csv.writer(memory_file)

            if filter_ == "all":
                csv_writer.writerow(['sequence', 'chem_comp_ID', 'H_shift', 'N_shift', 'H_atom_name', 'N_atom_name'])
                csv_writer.writerows([[_['sequence'], _['chem_comp_ID'], _['H_shift'], _['N_shift'],
                                       _['H_atom_name'], _['N_atom_name']] for _ in dict_format])
            else:
                csv_writer.writerow(['sequence', 'chem_comp_ID', 'H_shift', 'N_shift'])
                csv_writer.writerows([[_['sequence'], _['chem_comp_ID'], _['H_shift'], _['N_shift']] for _ in
                                      dict_format])

            memory_file.seek(0)
            response = Response(memory_file.read(), mimetype='text/csv')
            response.headers.set("Content-Disposition", 'attachment',
                                 filename=f'{entry_id}_simulated_hsqc_{filter_}.csv')
            return response


@entry_endpoints.route('/entry/<entry_id>/validate')
def validate_entry(entry_id):
    """ Returns the validation report for the given entry. """

    try:
        entry_id, entry = next(querymod.get_valid_entries_from_redis(entry_id))
    except StopIteration:
        raise RequestException("Entry '%s' does not exist in the public database." % entry_id)

    result = {entry_id: {'avs': {}}}
    # Put the chemical shift loop in a file
    with tempfile.NamedTemporaryFile(dir="/dev/shm") as star_file:
        star_file.write(str(entry).encode())
        star_file.flush()

        avs_location = os.path.join(querymod.SUBMODULE_DIR, "avs/validate_assignments_31.pl")
        res = subprocess.check_output([avs_location, entry_id, "-nitrogen", "-fmean",
                                       "-aromatic", "-std", "-anomalous", "-suspicious",
                                       "-star_output", star_file.name])

        error_loop = pynmrstar.Entry.from_string(res.decode())
        try:
            error_loop = error_loop.get_loops_by_category("_AVS_analysis_r")[0]
            error_loop = error_loop.filter(["Assembly_ID", "Entity_assembly_ID",
                                            "Entity_ID", "Comp_index_ID",
                                            "Comp_ID",
                                            "Comp_overall_assignment_score",
                                            "Comp_typing_score",
                                            "Comp_SRO_score",
                                            "Comp_1H_shifts_analysis_status",
                                            "Comp_13C_shifts_analysis_status",
                                            "Comp_15N_shifts_analysis_status"])
            error_loop.category = "AVS_analysis"

            # Modify the chemical shift loops with the new data
            shift_lists = entry.get_loops_by_category("atom_chem_shift")
            for loop in shift_lists:
                loop.add_tag(["AVS_analysis_status", "PANAV_analysis_status"])
                for row in loop.data:
                    row.extend(["Consistent", "Consistent"])

            result[entry_id]["avs"] = error_loop.get_json(serialize=False)
        except IndexError:
            result[entry_id]["avs"] = {'error': "AVS failed to run on this entry."}

    # PANAV
    # For each chemical shift loop
    for pos, cs_loop in enumerate(entry.get_loops_by_category("atom_chem_shift")):

        # There is at least one chem shift saveframe for this entry
        result[entry_id]["panav"] = {}
        # Put the chemical shift loop in a file
        with tempfile.NamedTemporaryFile(dir="/dev/shm") as chem_shifts:
            chem_shifts.write(str(cs_loop).encode())
            chem_shifts.flush()

            panav_location = os.path.join(querymod.SUBMODULE_DIR, "panav/panav.jar")
            try:
                res = subprocess.check_output(["java", "-cp", panav_location, "CLI", "-f", "star", "-i",
                                               chem_shifts.name], stderr=subprocess.STDOUT)
                # There is a -j option that produces a somewhat usable JSON...
                result[entry_id]["panav"][pos] = panav_parser(res)
            except subprocess.CalledProcessError:
                result[entry_id]["panav"][pos] = {"error": "PANAV failed on this entry."}

    return jsonify(result)


@entry_endpoints.route('/list_entries')
def list_entries():
    """ Returns all valid entry IDs by default. If a database is specified than
        only entries from that database are returned. """

    db = querymod.get_db("combined")
    with RedisConnection() as r:
        return jsonify(r.lrange("%s:entry_list" % db, 0, -1))
