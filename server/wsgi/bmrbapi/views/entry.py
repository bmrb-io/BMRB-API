import tempfile

from flask import Blueprint, Response, request, jsonify, send_file
from pybmrb import csviz

from bmrbapi.exceptions import RequestException
from bmrbapi.utils import querymod

# Set up the blueprint
entry_endpoints = Blueprint('entry', __name__)


@entry_endpoints.route('/entry', methods=['POST'])
@entry_endpoints.route('/entry/<entry_id>', methods=['GET'])
def get_entry(entry_id=None):
    """ Returns an entry in the specified format."""

    # Get the format they want the results in
    format_ = request.args.get('format', "json")

    # If they are storing
    if request.method == "POST":
        return jsonify(querymod.store_uploaded_entry())

    # Loading
    else:
        if entry_id is None:
            # They didn't specify an entry ID
            raise RequestException("You must specify the entry ID.")

        # Make sure it is a valid entry
        if not querymod.check_valid(entry_id):
            raise RequestException("Entry '%s' does not exist in the public database." % entry_id,
                                   status_code=404)

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
            result = querymod.get_saveframes_by_category(ids=entry_id, keys=request.args.getlist('saveframe_category'),
                                                         format=format_)
            return jsonify(result)

        # See if they are requesting one or more saveframe
        elif request.args.get('saveframe_name', None):
            result = querymod.get_saveframes_by_name(ids=entry_id, keys=request.args.getlist('saveframe_name'),
                                                     format=format_)
            return jsonify(result)

        # See if they are requesting one or more loop
        elif request.args.get('loop', None):
            return jsonify(querymod.get_loops(ids=entry_id, keys=request.args.getlist('loop'), format=format_))

        # See if they want a tag
        elif request.args.get('tag', None):
            return jsonify(querymod.get_tags(ids=entry_id, keys=request.args.getlist('tag')))

        # They want an entry
        else:
            # Get the entry
            entry = querymod.get_entries(ids=entry_id, format=format_)

            # Bypass JSON encode/decode cycle
            if format_ == "json":
                return Response("""{"%s": %s}""" % (entry_id, entry[entry_id].decode()),
                                mimetype="application/json")

            # Special case to return raw nmrstar
            elif format_ == "rawnmrstar":
                return Response(entry[entry_id], mimetype="text/nmrstar")

            # Special case for raw zlib
            elif format_ == "zlib":
                return Response(entry[entry_id], mimetype="application/zlib")

            # Return the entry in any other format
            return jsonify(entry)


@entry_endpoints.route('/entry/<entry_id>/software')
def get_software_by_entry(entry_id=None):
    """ Returns the software used on a per-entry basis. """

    if not entry_id:
        raise RequestException("You must specify the entry ID.")

    return jsonify(querymod.get_entry_software(entry_id))


@entry_endpoints.route('/entry/<entry_id>/experiments')
def get_metabolomics_data(entry_id):
    """ Return the experiments available for an entry. """

    return jsonify(querymod.get_experiments(entry=entry_id))


@entry_endpoints.route('/entry/<entry_id>/citation')
def get_citation(entry_id):
    """ Return the citation information for an entry in the requested format. """

    format_ = request.args.get('format', "python")
    if format_ == "json-ld":
        format_ = "python"

    # Get the citation
    citation = querymod.get_citation(entry_id, format_=format_)

    # Bibtex
    if format_ == "bibtex":
        return Response(citation, mimetype="application/x-bibtex",
                        headers={"Content-disposition": "attachment; filename=%s.bib" % entry_id})
    elif format_ == "text":
        return Response(citation, mimetype="text/plain")
    # JSON+LD
    else:
        return jsonify(citation)


@entry_endpoints.route('/entry/<entry_id>/simulate_hsqc')
def simulate_hsqc(entry_id):
    """ Returns the html for a simulated HSQC spectrum. """

    csviz._AUTOOPEN = False
    csviz._OPACITY = 1
    with tempfile.NamedTemporaryFile(suffix='.html') as output_file:
        csviz.Spectra().n15hsqc(entry_id, outfilename=output_file.name)

        return send_file(output_file.name)


@entry_endpoints.route('/entry/<entry_id>/validate')
def validate_entry(entry_id):
    """ Returns the validation report for the given entry. """

    return jsonify(querymod.get_chemical_shift_validation(ids=entry_id))


@entry_endpoints.route('/list_entries')
def list_entries():
    """ Return a list of all valid BMRB entries."""

    valid_list = ['metabolomics', 'macromolecules', 'chemcomps', 'combined']
    entries = querymod.list_entries(database=querymod.get_db("combined", valid_list=valid_list))
    return jsonify(entries)
