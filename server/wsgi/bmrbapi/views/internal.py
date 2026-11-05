import json
import os
import re
import uuid

import pynmrstar
from flask import Blueprint, redirect, url_for, request, jsonify
from werkzeug.utils import secure_filename

from bmrbapi.exceptions import RequestException, ServerException
from bmrbapi.utils.configuration import configuration
from bmrbapi.utils.connections import RedisConnection
from bmrbapi.utils.querymod import locate_entry

internal_endpoints = Blueprint('internal', __name__)

# This endpoint is reachable by anyone: the depositor-facing page at
#  /deposit/timedomain_upload/ posts to it straight from the browser, so there is no
#  host or credential to check. Everything it accepts is therefore bounded here.
_MAX_TIMEDOMAIN_FILES = 200
_MAX_EMAIL_LENGTH = 320
# Deliberately strict: these are the only shapes a released BMRB ID takes, and the value
#  decides which Redis key we look up and what ends up in the curator's meta.str.
_ENTRY_ID_RE = re.compile(r'^(bmse|bmst)?[0-9]{1,12}$')


@internal_endpoints.route('/favicon.ico')
def favicon_internal():
    """ Return the favicon. """

    return redirect(url_for('static', filename='favicon.ico'))


def _validated_entry_id() -> str:
    """ Returns the entry ID the upload is for, having checked that it is a released
    entry. The upload page checks this client-side; an upload that skipped the page
    would otherwise file raw data against an arbitrary string. """

    entry_id = request.form.get('entry_id', '').strip()
    if not entry_id:
        raise RequestException('You must specify the entry_id that this data belongs to.')
    if not _ENTRY_ID_RE.match(entry_id):
        raise RequestException("Invalid entry_id: '%s'." % entry_id)

    with RedisConnection() as r:
        if not r.exists(locate_entry(entry_id, r_conn=r)):
            raise RequestException("Entry '%s' does not exist in the public database." % entry_id,
                                   status_code=404)

    return entry_id


def _validated_selections(name_mapping: dict) -> dict:
    """ Returns the file -> experiment mapping from the request, having checked that it
    is the shape we expect and only names files that were actually uploaded. """

    try:
        selections = json.loads(request.form.get('selections', '{}'))
    except ValueError:
        raise RequestException("Invalid 'selections' submitted. It must be JSON.")

    if not isinstance(selections, dict):
        raise RequestException("Invalid 'selections' submitted. It must be a JSON object.")

    for file_name, experiments in selections.items():
        if file_name not in name_mapping:
            raise RequestException("The 'selections' refer to a file that was not uploaded: '%s'." % file_name)
        if not isinstance(experiments, list) or not all(isinstance(_, (str, int)) for _ in experiments):
            raise RequestException("Invalid 'selections' submitted. Each value must be a list of experiment IDs.")

    return selections


@internal_endpoints.post('/timedomain')
def timedomain_internal():
    """ Accepts time domain data for an existing, released entry. Each upload lands in
    its own directory alongside a meta.str describing it, for a curator to pick up. """

    try:
        deposition_directory = configuration['timedomain_deposition_directory']
    except KeyError:
        raise ServerException('Timedomain deposition directory not configured on server, '
                              'please contact admins.')

    if not os.path.isdir(deposition_directory):
        raise ServerException('Timedomain deposition directory not present on server, '
                              'please contact admins.')

    # Validate everything before creating the directory, so that a rejected upload
    #  doesn't leave an empty one behind.
    entry_id = _validated_entry_id()

    email = request.form.get('email', 'unknown').strip() or 'unknown'
    if len(email) > _MAX_EMAIL_LENGTH:
        raise RequestException('The submitted e-mail address is too long.')

    uploaded_files = list(request.files.to_dict().values())
    if not uploaded_files:
        raise RequestException('No files uploaded. Please attach the time domain data to upload.')
    if len(uploaded_files) > _MAX_TIMEDOMAIN_FILES:
        raise RequestException('Too many files uploaded at once. Please upload %d or fewer files, or combine '
                               'them into an archive.' % _MAX_TIMEDOMAIN_FILES)

    # Work out the name each file will be stored under before writing anything.
    #  secure_filename() can reduce a name to the empty string (consider '..'), and it can
    #  map two different names onto one, so neither its result nor 'meta.str' may collide.
    name_mapping = {}
    used_names = {'meta.str'}
    for position, file in enumerate(uploaded_files):
        secured_filename = secure_filename(file.filename or '')
        if not secured_filename:
            secured_filename = 'upload_%d' % position
        while secured_filename in used_names:
            secured_filename = 'dup_%d_%s' % (position, secured_filename)
        used_names.add(secured_filename)
        name_mapping[file.filename] = secured_filename

    selections = _validated_selections(name_mapping)

    # Make the directory and put the data there
    outdir = os.path.join(deposition_directory, str(uuid.uuid4()))
    os.mkdir(outdir)

    for file in uploaded_files:
        file.save(os.path.join(outdir, name_mapping[file.filename]))

    # Write out the metadata
    meta = pynmrstar.Saveframe.from_scratch('timedomain_addition', tag_prefix='timedomain_upload')
    meta['Entry_ID'] = entry_id
    # Not verified - it is whatever the submitter typed into the upload page.
    meta['Author_Email'] = email

    loop = pynmrstar.Loop.from_scratch('_Experiment_file')
    loop.add_tag(['Experiment_ID', 'Name', 'Type'])
    for selection, values in selections.items():
        for value in values:
            loop.add_data([value, name_mapping[selection], 'Time-domain (raw spectral data)'])
    meta.add_loop(loop)

    meta.write_to_file(os.path.join(outdir, 'meta.str'))
    return jsonify('Successfully uploaded your data!')
