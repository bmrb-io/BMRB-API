#!/usr/bin/python

""" This code is used to provide the REST API interface. Under the hood
all of the work is done in utils/querymod.py - this just routes the queries
to the correct location and passes the results back."""

from __future__ import print_function

import os
import sys
import time
import datetime
import traceback
import logging
from logging.handlers import RotatingFileHandler, SMTPHandler
from uuid import uuid4

import requests
from itsdangerous import URLSafeSerializer, BadSignature
from pythonjsonlogger import jsonlogger
from validate_email import validate_email

try:
    import simplejson as json
except ImportError:
    import json

# Import flask
from flask import Flask, request, Response, jsonify, url_for, redirect, send_file
from werkzeug.utils import secure_filename
from flask_mail import Mail, Message

# Set up paths for imports and such
local_dir = os.path.dirname(__file__)
os.chdir(local_dir)
sys.path.append(local_dir)

# Import the functions needed to service requests - must be after path updates
from utils import querymod
pynmrstar = querymod.pynmrstar
from utils import depositions

# Set up the flask application
application = Flask(__name__)

# Set debug if running from command line
if application.debug:
    from flask_cors import CORS

    querymod.configuration['debug'] = True
    CORS(application)

application.secret_key = querymod.configuration['secret_key']

# Set up the logging

# First figure out where to log
request_log_file = os.path.join(local_dir, "logs", "requests.log")
application_log_file = os.path.join(local_dir, "logs", "application.log")
request_json_file = os.path.join(local_dir, "logs", "json_requests.log")
if querymod.configuration.get('log'):
    if querymod.configuration['log'].get('json'):
        request_json_file = querymod.configuration['log']['json']
    if querymod.configuration['log'].get('request'):
        request_log_file = querymod.configuration['log']['request']
    if querymod.configuration['log'].get('application'):
        application_log_file = querymod.configuration['log']['application']

# Set up the standard logger
app_formatter = logging.Formatter('[%(asctime)s]:%(levelname)s:%(funcName)s: %(message)s')
application_log = RotatingFileHandler(application_log_file, maxBytes=1048576, backupCount=100)
application_log.setFormatter(app_formatter)
application.logger.addHandler(application_log)
application.logger.setLevel(logging.WARNING)

# Set up the request loggers

# Plain text logger
request_formatter = logging.Formatter('[%(asctime)s]: %(message)s')
request_log = RotatingFileHandler(request_log_file, maxBytes=1048576, backupCount=100)
request_log.setFormatter(request_formatter)
rlogger = logging.getLogger("rlogger")
rlogger.setLevel(logging.INFO)
rlogger.addHandler(request_log)
rlogger.propagate = False

# JSON logger
json_formatter = jsonlogger.JsonFormatter()
application_json = RotatingFileHandler(request_json_file, maxBytes=1048576, backupCount=100)
application_json.setFormatter(json_formatter)
jlogger = logging.getLogger("jlogger")
jlogger.setLevel(logging.INFO)
jlogger.addHandler(application_json)
jlogger.propagate = False

# Set up the SMTP handler
if (querymod.configuration.get('smtp')
        and querymod.configuration['smtp'].get('server')
        and querymod.configuration['smtp'].get('admins')):

    # Don't send error e-mails in debugging mode
    if not querymod.configuration['debug']:
        mail_handler = SMTPHandler(mailhost=querymod.configuration['smtp']['server'],
                                   fromaddr='apierror@webapi.bmrb.wisc.edu',
                                   toaddrs=querymod.configuration['smtp']['admins'],
                                   subject='BMRB API Error occurred')
        mail_handler.setLevel(logging.WARNING)
        application.logger.addHandler(mail_handler)

    # Set up the mail interface
    application.config.update(
        MAIL_SERVER=querymod.configuration['smtp']['server'],
        # TODO: Make this configurable
        MAIL_DEFAULT_SENDER='noreply@bmrb.wisc.edu'
    )
    mail = Mail(application)
else:
    logging.warning("Could not set up SMTP logger because the configuration"
                    " was not specified.")


# Set up error handling
@application.errorhandler(querymod.ServerError)
@application.errorhandler(querymod.RequestError)
def handle_our_errors(error):
    """ Handles exceptions we raised ourselves. """

    application.logger.info("Handled error raised in %s: %s", request.url, error.message)

    response = jsonify(error.to_dict())
    response.status_code = error.status_code
    return response


@application.errorhandler(Exception)
def handle_other_errors(error):
    """ Catches any other exceptions and formats them. Only
    displays the actual error to local clients (to prevent disclosing
    issues that could be security vulnerabilities)."""

    application.logger.critical("Unhandled exception raised on request %s %s"
                                "\n\nValues: %s\n\n%s",
                                request.method, request.url,
                                request.values,
                                traceback.format_exc())

    if check_local_ip():
        return Response("NOTE: You are seeing this error because your IP was "
                        "recognized as a local IP:\n%s" %
                        traceback.format_exc(), mimetype="text/plain")
    else:
        response = jsonify({"error": "Server error. Contact webmaster@bmrb.wisc.edu."})
        response.status_code = 500
        return response


# Set up logging
@application.before_request
def log_request():
    """ Log all requests. """
    rlogger.info("%s %s %s %s %s", request.remote_addr, request.method,
                 request.full_path,
                 request.headers.get('User-Agent', '?').split()[0],
                 request.headers.get('Application', 'unknown'))

    jlogger.info({"user-agent": request.headers.get('User-Agent'),
                  "method": request.method, "endpoint": request.endpoint,
                  "application": request.headers.get('Application'),
                  "path": request.full_path, "ip": request.remote_addr,
                  "local": check_local_ip(), "time": time.time()})

    # Don't pretty-print JSON unless local user and in debug mode
    application.config['JSONIFY_PRETTYPRINT_REGULAR'] = (check_local_ip() and
                                                         querymod.configuration['debug']) or request.args.get(
        "prettyprint") == "true"


@application.route('/favicon.ico')
def favicon():
    """ Return the favicon. """

    return redirect(url_for('static', filename='favicon.ico'))


@application.route('/')
def no_params():
    """ Return an error if they have not specified which method type to use."""

    result = ""
    for method in querymod._METHODS:
        result += '<a href="%s">%s</a><br>' % (method, method)

    return result


@application.route('/list_entries')
def list_entries():
    """ Return a list of all valid BMRB entries."""

    entries = querymod.list_entries(database=get_db("combined",
                                                    valid_list=['metabolomics',
                                                                'macromolecules',
                                                                'chemcomps',
                                                                'combined']))
    return jsonify(entries)


@application.route('/deposition/<uuid:uuid>/resend-validation-email')
def send_validation_email(uuid):
    """ Sends the validation e-mail. """

    uuid = str(uuid)

    with depositions.DepositionRepo(uuid) as repo:
        # Already validated, don't re-send the email
        if repo.metadata['email_validated']:
            return jsonify({'status': 'validated'})
        # Ask them to confirm their e-mail
        confirm_message = Message("Please validate your e-mail address for BMRBDep deposition '%s'." %
                                  repo.metadata['deposition_nickname'],
                                  recipients=[repo.metadata['author_email']])
        token = URLSafeSerializer(querymod.configuration['secret_key']).dumps({'deposition_id': uuid})

        confirm_message.html = \
"""Thank you for your deposition '%s' created %s (UTC).
<br><br>
Please click <a href="%s">here</a> to validate your e-mail for this session. This is required to proceed.
<br><br>
You can use <a href="%s">this link</a> to return to your deposition later if you close the page before it is complete.
<br><br>
If you wish to share access with collaborators, simply forward them this e-mail. Be aware that anyone you
share this e-mail with will have access to the full contents of your in-progress deposition and can make
changes to it.
<br><br>
Thank you,
<br>
BMRBDep System""" % (repo.metadata['deposition_nickname'], repo.metadata['creation_date'],
                     url_for('validate_user', token=token, _external=True),
                     # TODO: Make this URL configurable
                     'http://dev-bmrbdep.bmrb.wisc.edu/entry/%s/saveframe/deposited_data_files/category' % uuid)

        mail.send(confirm_message)

    return jsonify({'status': 'unvalidated'})


@application.route('/deposition/validate_email/<token>')
def validate_user(token):
    """ Validate a user-email. """

    serializer = URLSafeSerializer(application.config['SECRET_KEY'])
    try:
        deposition_data = serializer.loads(token)
        deposition_id = deposition_data['deposition_id']
    except (BadSignature, KeyError, TypeError):
        raise querymod.RequestError('Invalid e-mail validation token. Please request a new e-mail validation message.')

    with depositions.DepositionRepo(deposition_id) as repo:
        if not repo.metadata['email_validated']:
            repo.metadata['email_validated'] = True
            repo.commit("E-mail validated.")

    return redirect('http://dev-bmrbdep.bmrb.wisc.edu/entry/%s/saveframe/deposited_data_files/category' % deposition_id,
                    code=302)


@application.route('/deposition/new', methods=('POST',))
def new_deposition():
    """ Starts a new deposition. """

    request_info = request.form

    if not request_info or 'email' not in request_info:
        raise querymod.RequestError("Must specify user e-mail to start a session.")

    if 'deposition_nickname' not in request_info:
        raise querymod.RequestError("Must specify a nickname for the deposition.")

    uploaded_entry = None
    entry_bootstrap = False
    if 'nmrstar_file' in request.files and request.files['nmrstar_file'] and request.files['nmrstar_file'].filename:
        try:
            uploaded_entry = pynmrstar.Entry.from_string(request.files['nmrstar_file'].read())
        except ValueError as e:
            return querymod.RequestError("Invalid NMR-STAR file. Parse error: %s" % e.message)
    # Check if they are bootstrapping from an existing entry - if so, make sure they didn't also upload a file
    if 'bootstrapID' in request_info and request_info['bootstrapID'] != 'null':
        if uploaded_entry:
            raise querymod.RequestError('Cannot create an entry from an uploaded file and existing entry.')
        try:
            uploaded_entry = pynmrstar.Entry.from_database(request_info['bootstrapID'])
        except IOError:
            raise querymod.RequestError('Invalid entry ID specified. No such entry exists, or is released.')
        entry_bootstrap = True

    author_email = request_info.get('email')
    author_orcid = request_info.get('orcid')
    if not author_orcid:
        author_orcid = None

    # Check the e-mail
    if not validate_email(author_email):
        raise querymod.RequestError("The e-mail you provided is not a valid e-mail. Please check the e-mail you "
                                    "provided for typos.")
    elif not validate_email(author_email, check_mx=True, smtp_timeout=3):
        raise querymod.RequestError("The e-mail you provided is invalid. There is no e-mail server at '%s'. (Do you "
                                    "have a typo in the part of your e-mail after the @?)" %
                                    (author_email[author_email.index("@") + 1:]))
    elif not validate_email(author_email, verify=True, sending_email='webmaster@bmrb.wisc.edu', smtp_timeout=3):
        raise querymod.RequestError("The e-mail you provided is invalid. That e-mail address does not exist at that "
                                    "server. (Do you have a typo in the e-mail address before the @?)")

    # Create the deposition
    deposition_id = str(uuid4())
    schema = pynmrstar.Schema()
    json_schema = querymod.get_schema(schema.version)
    entry_template = pynmrstar.Entry.from_template(entry_id=deposition_id, all_tags=True, default_values=True,
                                                   schema=schema)

    # Merge the entries
    if uploaded_entry:
        # Rename the saveframes in the uploaded entry before merging them
        for category in uploaded_entry.category_list:
            for x, saveframe in enumerate(uploaded_entry.get_saveframes_by_category(category)):
                # Set the "Name" tag if it isn't already set
                if (saveframe.tag_prefix + '.name').lower() in schema.schema:
                    try:
                        saveframe.add_tag('Name', saveframe['sf_framecode'][0].replace("_", " "), update=False)
                    except ValueError:
                        pass
                new_name = "%s_%s" % (saveframe.category, x + 1)
                if saveframe.name != new_name:
                    uploaded_entry.rename_saveframe(saveframe.name, new_name)

    # Merge the entries
    if uploaded_entry:
        for category in uploaded_entry.category_list:
            delete_saveframes = entry_template.get_saveframes_by_category(category)
            for saveframe in delete_saveframes:
                if saveframe.category == "entry_interview":
                    continue
                del entry_template[saveframe]
            for saveframe in uploaded_entry.get_saveframes_by_category(category):
                # Don't copy over the entry interview at all
                if saveframe.category == "entry_interview":
                    continue
                new_saveframe = pynmrstar.Saveframe.from_template(category, saveframe.name, deposition_id, True, schema)
                frame_prefix_lower = saveframe.tag_prefix.lower()

                # Don't copy the tags from entry_information
                if saveframe.category != "entry_information":
                    for tag in saveframe.tags:
                        lower_tag = tag[0].lower()
                        if lower_tag not in ['sf_category', 'sf_framecode', 'id', 'entry_id', 'nmr_star_version',
                                             'original_nmr_star_version']:
                            fqtn = frame_prefix_lower + '.' + lower_tag
                            if fqtn in schema.schema:
                                new_saveframe.add_tag(tag[0], tag[1], update=True)

                for loop in saveframe.loops:
                    if loop.category == "_Upload_data":
                        continue
                    lower_tags = [_.lower() for _ in loop.tags]
                    tags_to_pull = [_ for _ in new_saveframe[loop.category].tags if _.lower() in lower_tags]
                    filtered_original_loop = loop.filter(tags_to_pull)
                    filtered_original_loop.add_missing_tags(schema=schema, all_tags=True)
                    new_saveframe[filtered_original_loop.category] = filtered_original_loop
                entry_template.add_saveframe(new_saveframe)
        entry_template.normalize()

    # Set the entry information tags
    entry_information = entry_template.get_saveframes_by_category('entry_information')[0]
    entry_information['NMR_STAR_version'] = schema.version
    entry_information['Original_NMR_STAR_version'] = schema.version

    # Suggest some default sample conditions
    sample_conditions = entry_template.get_loops_by_category('_Sample_condition_variable')[0]
    if sample_conditions.empty:
        sample_conditions.data = [[None for _ in range(len(sample_conditions.tags))] for _ in range(4)]
        sample_conditions['Type'] = ['temperature', 'pH', 'pressure', 'ionic strength']
        sample_conditions['Val'] = [None, None, '1', None]
        sample_conditions['Val_units'] = ['K', 'pH', 'atm', 'M']

    author_given = None
    author_family = None

    # Look up information based on the ORCID
    if author_orcid:
        r = requests.get(querymod.configuration['orcid']['url'] % author_orcid,
                         headers={"Accept": "application/json",
                                  'Authorization': 'Bearer %s' % querymod.configuration['orcid']['bearer']})
        if not r.ok:
            if r.status_code == 404:
                raise querymod.RequestError('Invalid ORCID!')
            else:
                application.logger.exception('An error occurred while contacting the ORCID server.')
        orcid_json = r.json()
        author_given = orcid_json['person']['name']['given-names']['value']
        author_family = orcid_json['person']['name']['family-name']['value']

    entry_saveframe = entry_template.get_saveframes_by_category("entry_information")[0]
    entry_saveframe['UUID'] = deposition_id

    # Update the loops with the data we have
    author_loop = pynmrstar.Loop.from_scratch()
    author_loop.add_tag(['_Entry_author.Given_name',
                         '_Entry_author.Middle_initials',
                         '_Entry_author.Family_name',
                         '_Entry_author.ORCID'])
    author_loop.add_data([author_given,
                          None,
                          author_family,
                          author_orcid])
    if not entry_saveframe['_Entry_author'].empty:
        for row in entry_saveframe['_Entry_author'].get_tag(['_Entry_author.Given_name',
                                                             '_Entry_author.Middle_initials'
                                                             '_Entry_author.Family_name',
                                                             '_Entry_author.ORCID']):
            author_loop.add_data(row)

    author_loop.add_missing_tags(all_tags=True, schema=schema)
    author_loop.sort_tags()
    entry_saveframe['_Entry_author'] = author_loop

    contact_loop = pynmrstar.Loop.from_scratch()
    contact_loop.add_tag(['_Contact_person.Given_name',
                          '_Contact_person.Middle_initials',
                          '_Contact_person.Family_name',
                          '_Contact_person.ORCID',
                          '_Contact_person.Email_address'])
    contact_loop.add_data([author_given,
                           None,
                           author_family,
                           author_orcid,
                           author_email])
    contact_loop.add_data([None, None, None, None, None])
    # Merge the uploaded data
    if not entry_saveframe['_Contact_person'].empty:
        for row in entry_saveframe['_Contact_person'].get_tag(['_Contact_person.Given_name',
                                                               '_Contact_person.Middle_initials'
                                                               '_Contact_person.Family_name',
                                                               '_Contact_person.ORCID',
                                                               '_Contact_person.Email_address']):
            contact_loop.add_data(row)
    contact_loop.add_missing_tags(all_tags=True, schema=schema)
    contact_loop.sort_tags()
    entry_saveframe['_Contact_person'] = contact_loop

    # Set the loops to have at least one row of data
    for saveframe in entry_template:

        # Add a "deleted" tag to use to track deletion status
        saveframe.add_tag('_Deleted', 'no')

        for loop in saveframe:
            if not loop.data:
                row_data = []
                for tag in loop.tags:
                    fqtn = (loop.category + '.' + tag).lower()
                    if schema.schema[fqtn]['default value'] not in ["?", '']:
                        row_data.append(schema.schema[fqtn]['default value'])
                    else:
                        row_data.append('.')
                loop.data = [row_data]

    # Set the entry_interview tags
    entry_interview = entry_template.get_saveframes_by_category('entry_interview')[0]
    for tag in json_schema['file_upload_types']:
        entry_interview[tag[2]] = "no"
    entry_interview['PDB_deposition'] = "no"
    entry_interview['BMRB_deposition'] = "yes"
    # Set the tag to store that this entry was bootstrapped
    if entry_bootstrap:
        entry_interview['Previous_BMRB_entry_used'] = request_info['bootstrapID']

    entry_meta = {'deposition_id': deposition_id,
                  'author_email': author_email,
                  'author_orcid': author_orcid,
                  'last_ip': request.environ['REMOTE_ADDR'],
                  'deposition_origination': {'request': dict(request.headers),
                                             'ip': request.environ['REMOTE_ADDR']},
                  'email_validated': False,
                  'schema_version': schema.version,
                  'entry_deposited': False,
                  'creation_date': datetime.datetime.utcnow().strftime("%I:%M %p on %B %d, %Y"),
                  'deposition_nickname': request_info['deposition_nickname'],
                  'deposition_from_file': True if uploaded_entry else False}
    if uploaded_entry:
        if entry_bootstrap:
            entry_meta['bootstrap_entry'] = request_info['bootstrapID']
        else:
            entry_meta['bootstrap_filename'] = request.files['nmrstar_file'].filename

    # Initialize the repo
    with depositions.DepositionRepo(deposition_id, initialize=True) as repo:
        # Manually set the metadata during object creation - never should be done this way elsewhere
        repo._live_metadata = entry_meta
        repo.write_entry(entry_template)
        repo.write_file('schema.json', json.dumps(json_schema), root=True)
        if uploaded_entry:
            if entry_bootstrap:
                repo.write_file('bootstrap_entry.str', str(uploaded_entry), root=True)
            else:
                request.files['nmrstar_file'].seek(0)
                repo.write_file('bootstrap_entry.str', request.files['nmrstar_file'].read(), root=True)
        repo.commit("Entry created.")

    # Send the validation e-mail
    send_validation_email(deposition_id)

    return jsonify({'deposition_id': deposition_id})


@application.route('/deposition/<uuid:uuid>/deposit', methods=('POST',))
def deposit_entry(uuid):
    """ Complete the deposition! """

    with depositions.DepositionRepo(uuid) as repo:
        if repo.metadata['entry_deposited']:
            raise querymod.RequestError('Entry already deposited, no changes allowed.')
        if not repo.metadata['email_validated']:
            raise querymod.RequestError('Please click confirm on the e-mail validation '
                                        'link you were sent prior to deposition.')
        repo.metadata['entry_deposited'] = True
        repo.commit('Deposition submitted!')

        # Ask them to confirm their e-mail
        message = Message("Your entry has been deposited!", recipients=[repo.metadata['author_email']])
        message.html = 'Thank you for your deposition! The NMR-STAR representation of your entry is attached. You ' +\
                       'will hear from our annotators in the next few days.'
        message.attach("%s.str" % uuid, "text/plain", str(repo.get_entry()))
        mail.send(message)

    return jsonify({'status': 'success'})


@application.route('/deposition/<uuid:uuid>/file/<filename>', methods=('GET', 'DELETE'))
def file_operations(uuid, filename):
    """ Either retrieve or delete a file. """

    if request.method == "GET":
        with depositions.DepositionRepo(uuid) as repo:
            return send_file(repo.get_file(filename, raw_file=True, root=False),
                             attachment_filename=secure_filename(filename))
    elif request.method == "DELETE":
        with depositions.DepositionRepo(uuid) as repo:
            if repo.metadata['entry_deposited']:
                raise querymod.RequestError('Entry already deposited, no changes allowed.')
            repo.delete_data_file(filename)
            repo.commit('Deleted file %s' % filename)
        return jsonify({'status': 'success'})


@application.route('/deposition/<uuid:uuid>/file', methods=('POST',))
def store_file(uuid):
    """ Stores a data file based on uuid. """

    file_obj = request.files.get('file', None)

    if not file_obj or not file_obj.filename:
        raise querymod.RequestError('No file uploaded!')

    # Store a data file
    with depositions.DepositionRepo(uuid) as repo:
        if repo.metadata['entry_deposited']:
            raise querymod.RequestError('Entry already deposited, no changes allowed.')

        filename = repo.write_file(file_obj.filename, file_obj.read())

        # Update the entry data
        if repo.commit("User uploaded file: %s" % filename):
            return jsonify({'filename': filename, 'changed': True})
        else:
            return jsonify({'filename': filename, 'changed': False})


@application.route('/deposition/<uuid:uuid>', methods=('GET', 'PUT'))
def fetch_or_store_deposition(uuid):
    """ Fetches or stores an entry based on uuid """

    # Store an entry
    if request.method == "PUT":
        try:
            entry = pynmrstar.Entry.from_json(request.get_json())
        except ValueError:
            raise querymod.RequestError("Invalid JSON uploaded. The JSON was not a valid NMR-STAR entry.")

        with depositions.DepositionRepo(uuid) as repo:
            if repo.metadata['entry_deposited']:
                raise querymod.RequestError('Entry already deposited, no changes allowed.')

            existing_entry = repo.get_entry()

            # If they aren't making any changes
            try:
                if existing_entry == entry:
                    return jsonify({'changed': False})
            except ValueError as err:
                raise querymod.RequestError(str(err))

            if existing_entry.entry_id != entry.entry_id:
                raise querymod.RequestError("Refusing to overwrite entry with entry of different ID.")

            # Update the entry data
            repo.write_entry(entry)
            repo.commit("Entry updated.")

            return jsonify({'changed': True})

    # Load an entry
    elif request.method == "GET":

        with depositions.DepositionRepo(uuid) as repo:
            entry = repo.get_entry()
            schema_version = entry.get_tag('_Entry.NMR_STAR_version')[0]
            data_files = repo.get_data_file_list()
        try:
            schema = querymod.get_schema(schema_version)
        except querymod.RequestError:
            raise querymod.ServerError("Entry specifies schema that doesn't exist on the "
                                       "server: %s" % schema_version)

        entry = entry.get_json(serialize=False)
        entry['schema'] = schema
        entry['data_files'] = data_files
        return jsonify(entry)


@application.route('/entry/', methods=('POST', 'GET'))
@application.route('/entry/<entry_id>')
def get_entry(entry_id=None):
    """ Returns an entry in the specified format."""

    # Get the format they want the results in
    format_ = request.args.get('format', "json")

    # If they are storing
    if request.method == "POST":
        return jsonify(querymod.store_uploaded_entry(request))

    # Loading
    else:
        if entry_id is None:
            # They are trying to send an entry using GET
            if request.args.get('data', None):
                raise querymod.RequestError("Cannot access this page through GET.")
            # They didn't specify an entry ID
            else:
                raise querymod.RequestError("You must specify the entry ID.")

        # Make sure it is a valid entry
        if not querymod.check_valid(entry_id):
            raise querymod.RequestError("Entry '%s' does not exist in the "
                                        "public database." % entry_id,
                                        status_code=404)

        # See if they specified more than one of [saveframe, loop, tag]
        args = sum([1 if request.args.get('saveframe_category', None) else 0,
                    1 if request.args.get('saveframe_name', None) else 0,
                    1 if request.args.get('loop', None) else 0,
                    1 if request.args.get('tag', None) else 0])
        if args > 1:
            raise querymod.RequestError("Request either loop(s), saveframe(s) by"
                                        " category, saveframe(s) by name, "
                                        "or tag(s) but not more than one "
                                        "simultaneously.")

        # See if they are requesting one or more saveframe
        elif request.args.get('saveframe_category', None):
            result = querymod.get_saveframes_by_category(ids=entry_id,
                                                         keys=request.args.getlist('saveframe_category'),
                                                         format=format_)
            return jsonify(result)

        # See if they are requesting one or more saveframe
        elif request.args.get('saveframe_name', None):
            result = querymod.get_saveframes_by_name(ids=entry_id,
                                                     keys=request.args.getlist('saveframe_name'),
                                                     format=format_)
            return jsonify(result)

        # See if they are requesting one or more loop
        elif request.args.get('loop', None):
            return jsonify(querymod.get_loops(ids=entry_id,
                                              keys=request.args.getlist('loop'),
                                              format=format_))

        # See if they want a tag
        elif request.args.get('tag', None):
            return jsonify(querymod.get_tags(ids=entry_id,
                                             keys=request.args.getlist('tag')))

        # They want an entry
        else:
            # Get the entry
            entry = querymod.get_entries(ids=entry_id, format=format_)

            # Bypass JSON encode/decode cycle
            if format_ == "json":
                return Response("""{"%s": %s}""" % (entry_id, entry[entry_id]),
                                mimetype="application/json")

            # Special case to return raw nmrstar
            elif format_ == "rawnmrstar":
                return Response(entry[entry_id], mimetype="text/nmrstar")

            # Special case for raw zlib
            elif format_ == "zlib":
                return Response(entry[entry_id], mimetype="application/zlib")

            # Return the entry in any other format
            return jsonify(entry)


@application.route('/schema')
@application.route('/schema/<schema_version>')
def return_schema(schema_version=None):
    """ Returns the BMRB schema as JSON. """
    return jsonify(querymod.get_schema(schema_version))


@application.route('/molprobity/')
@application.route('/molprobity/<pdb_id>')
@application.route('/molprobity/<pdb_id>/oneline')
def return_molprobity_oneline(pdb_id=None):
    """Returns the molprobity data for a PDB ID. """

    if not pdb_id:
        raise querymod.RequestError("You must specify the PDB ID.")

    return jsonify(querymod.get_molprobity_data(pdb_id))


@application.route('/molprobity/<pdb_id>/residue')
def return_molprobity_residue(pdb_id):
    """Returns the molprobity residue data for a PDB ID. """

    return jsonify(querymod.get_molprobity_data(pdb_id,
                                                residues=request.args.getlist('r')))


@application.route('/search')
@application.route('/search/')
def print_search_options():
    """ Returns a list of the search methods."""

    result = ""
    for method in ["chemical_shifts", "fasta", "get_all_values_for_tag",
                   "get_bmrb_data_from_pdb_id",
                   "get_id_by_tag_value", "get_bmrb_ids_from_pdb_id",
                   "get_pdb_ids_from_bmrb_id", "multiple_shift_search"]:
        result += '<a href="%s">%s</a><br>' % (method, method)

    return result


@application.route('/search/get_bmrb_data_from_pdb_id/')
@application.route('/search/get_bmrb_data_from_pdb_id/<pdb_id>')
def get_bmrb_data_from_pdb_id(pdb_id=None):
    """ Returns the associated BMRB data for a PDB ID. """

    if not pdb_id:
        raise querymod.RequestError("You must specify a PDB ID.")

    result = []
    for item in querymod.get_bmrb_ids_from_pdb_id(pdb_id):
        data = querymod.get_extra_data_available(item['bmrb_id'])
        if data:
            result.append({'bmrb_id': item['bmrb_id'], 'match_types': item['match_types'],
                           'url': 'http://www.bmrb.wisc.edu/data_library/summary/index.php?bmrbId=%s' % item['bmrb_id'],
                           'data': data})

    return jsonify(result)


@application.route('/search/multiple_shift_search')
def multiple_shift_search():
    """ Finds entries that match at least some of the peaks. """

    peaks = request.args.getlist('shift')
    if not peaks:
        peaks = request.args.getlist('s')
    else:
        peaks.extend(list(request.args.getlist('s')))

    if not peaks:
        raise querymod.RequestError("You must specify at least one shift to search for.")

    return jsonify(querymod.multiple_peak_search(peaks,
                                                 database=get_db("metabolomics")))


@application.route('/search/chemical_shifts')
def get_chemical_shifts():
    """ Return a list of all chemical shifts that match the selectors"""

    cs1d = querymod.chemical_shift_search_1d
    return jsonify(cs1d(shift_val=request.args.getlist('shift'),
                        threshold=request.args.get('threshold', .03),
                        atom_type=request.args.get('atom_type', None),
                        atom_id=request.args.getlist('atom_id'),
                        comp_id=request.args.getlist('comp_id'),
                        conditions=request.args.get('conditions', False),
                        database=get_db("macromolecules")))


@application.route('/search/get_all_values_for_tag/')
@application.route('/search/get_all_values_for_tag/<tag_name>')
def get_all_values_for_tag(tag_name=None):
    """ Returns all entry numbers and corresponding tag values."""

    result = querymod.get_all_values_for_tag(tag_name, get_db('macromolecules'))
    return jsonify(result)


@application.route('/search/get_id_by_tag_value/')
@application.route('/search/get_id_by_tag_value/<tag_name>/')
@application.route('/search/get_id_by_tag_value/<tag_name>/<path:tag_value>')
def get_id_from_search(tag_name=None, tag_value=None):
    """ Returns all BMRB IDs that were found when querying for entries
    which contain the supplied value for the supplied tag. """

    database = get_db('macromolecules',
                      valid_list=['metabolomics', 'macromolecules', 'chemcomps'])

    if not tag_name:
        raise querymod.RequestError("You must specify the tag name.")
    if not tag_value:
        raise querymod.RequestError("You must specify the tag value.")

    sp = tag_name.split(".")
    if sp[0].startswith("_"):
        sp[0] = sp[0][1:]
    if len(sp) < 2:
        raise querymod.RequestError("You must provide a full tag name with "
                                    "saveframe included. For example: "
                                    "Entry.Experimental_method_subtype")

    id_field = querymod.get_entry_id_tag(tag_name, database)
    result = querymod.select([id_field], sp[0], where_dict={sp[1]: tag_value},
                             modifiers=['lower'], database=database)
    return jsonify(result[result.keys()[0]])


@application.route('/search/get_bmrb_ids_from_pdb_id/')
@application.route('/search/get_bmrb_ids_from_pdb_id/<pdb_id>')
def get_bmrb_ids_from_pdb_id(pdb_id=None):
    """ Returns the associated BMRB IDs for a PDB ID. """

    if not pdb_id:
        raise querymod.RequestError("You must specify a PDB ID.")

    result = querymod.get_bmrb_ids_from_pdb_id(pdb_id)
    return jsonify(result)


@application.route('/search/get_pdb_ids_from_bmrb_id/')
@application.route('/search/get_pdb_ids_from_bmrb_id/<pdb_id>')
def get_pdb_ids_from_bmrb_id(pdb_id=None):
    """ Returns the associated BMRB IDs for a PDB ID. """

    if not pdb_id:
        raise querymod.RequestError("You must specify a BMRB ID.")

    result = querymod.get_pdb_ids_from_bmrb_id(pdb_id)
    return jsonify(result)


@application.route('/search/fasta/')
@application.route('/search/fasta/<query>')
def fasta_search(query=None):
    """Performs a FASTA search on the specified query in the BMRB database."""

    if not query:
        raise querymod.RequestError("You must specify a sequence.")

    return jsonify(querymod.fasta_search(query,
                                         a_type=request.args.get('type', 'polymer'),
                                         e_val=request.args.get('e_val')))


@application.route('/enumerations/')
@application.route('/enumerations/<tag_name>')
def get_enumerations(tag_name=None):
    """ Returns all enumerations for a given tag."""

    if not tag_name:
        raise querymod.RequestError("You must specify the tag name.")

    return jsonify(querymod.get_enumerations(tag=tag_name,
                                             term=request.args.get('term')))


@application.route('/select', methods=('GET', 'POST'))
def select():
    """ Performs an advanced select query. """

    # Check for GET request
    if request.method == "GET":
        raise querymod.RequestError("Cannot access this page through GET.")

    data = json.loads(request.get_data(cache=False, as_text=True))

    return jsonify(querymod.process_select(**data))


@application.route('/software/')
def get_software_summary():
    """ Returns a summary of all software used in all entries. """

    return jsonify(querymod.get_software_summary())


# Software queries
@application.route('/entry/<entry_id>/software')
def get_software_by_entry(entry_id=None):
    """ Returns the software used on a per-entry basis. """

    if not entry_id:
        raise querymod.RequestError("You must specify the entry ID.")

    return jsonify(querymod.get_entry_software(entry_id))


@application.route('/software/package/')
@application.route('/software/package/<package_name>')
def get_software_by_package(package_name=None):
    """ Returns the entries that used a particular software package. Search
    is done case-insensitive and is an x in y search rather than x == y
    search. """

    if not package_name:
        raise querymod.RequestError("You must specify the software package name.")

    return jsonify(querymod.get_software_entries(package_name,
                                                 database=get_db('macromolecules')))


@application.route('/entry/<entry_id>/experiments')
def get_metabolomics_data(entry_id):
    """ Return the experiments available for an entry. """

    return jsonify(querymod.get_experiments(entry=entry_id))


@application.route('/entry/<entry_id>/citation')
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


@application.route('/instant')
def get_instant():
    """ Do the instant search. """

    if not request.args.get('term', None):
        raise querymod.RequestError("You must specify the search term using ?term=search_term")

    return jsonify(querymod.get_instant_search(term=request.args.get('term'),
                                               database=get_db('combined')))


@application.route('/status')
def get_status():
    """ Returns the server status."""

    status = querymod.get_status()

    if check_local_ip():
        # Raise an exception to test SMTP error notifications working
        if request.args.get("exception"):
            raise Exception("Unhandled exception test.")

        status['URL'] = request.url
        status['secure'] = request.is_secure
        status['remote_address'] = request.remote_addr
        status['debug'] = querymod.configuration.get('debug')

    return jsonify(status)


# Queries that run commands
@application.route('/entry/<entry_id>/validate')
def validate_entry(entry_id=None):
    """ Returns the validation report for the given entry. """

    if not entry_id:
        raise querymod.RequestError("You must specify the entry ID.")

    return jsonify(querymod.get_chemical_shift_validation(ids=entry_id))


# Helper methods
def get_db(default="macromolecules",
           valid_list=None):
    """ Make sure the DB specified is valid. """

    if not valid_list:
        valid_list = ["metabolomics", "macromolecules", "combined", "chemcomps"]

    database = request.args.get('database', default)

    if database not in valid_list:
        raise querymod.RequestError("Invalid database: %s." % database)

    return database


def check_local_ip():
    """ Checks if the given IP is a local user."""

    for local_address in querymod.configuration['local-ips']:
        if request.remote_addr.startswith(local_address):
            return True

    return False
