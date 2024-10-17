import json
import os
import uuid

import pynmrstar
from flask import Blueprint, redirect, url_for, request, jsonify
from werkzeug.utils import secure_filename

from bmrbapi import configuration

internal_endpoints = Blueprint('internal', __name__)


@internal_endpoints.route('/favicon.ico')
def favicon_internal():
    """ Return the favicon. """

    return redirect(url_for('static', filename='favicon.ico'))


@internal_endpoints.post('/timedomain')
def timedomain_internal():
    try:
        outdir = os.path.join(configuration['timedomain_deposition_directory'], str(uuid.uuid4()))
    except KeyError:
        raise IOError('Timedomain deposition directory not present on server, please contact admins.')

    # Make the directory and put the data there
    os.mkdir(outdir)

    name_mapping = {}

    # Write out all uploaded files to the outdir, sanitizing their name if necessary
    for file in request.files.to_dict().values():
        secured_filename = secure_filename(file.filename)
        name_mapping[file.filename] = secured_filename
        file.save(os.path.join(outdir, secured_filename))

    # Write out the metadata
    meta = pynmrstar.Saveframe.from_scratch('timedomain_addition', tag_prefix='timedomain_upload')
    meta['Entry_ID'] = request.form.get('entry_id', 'unknown')
    meta['Author_Email'] = request.form.get('email', 'unknown')

    loop = pynmrstar.Loop.from_scratch('_Experiment_file')
    loop.add_tag(['Experiment_ID', 'Name', 'Type'])
    for selection, values in json.loads(request.form.get('selections', '{}')).items():
        for value in values:
            loop.add_data([value, name_mapping[selection], 'Time-domain (raw spectral data)'])
    meta.add_loop(loop)

    meta.write_to_file(os.path.join(outdir, 'meta.str'))
    return jsonify('Successfully uploaded your data!')
