#!/usr/bin/env python3

""" This code is used to provide the REST API interface. Under the hood
all of the work is done in utils/querymod.py - this just routes the queries
to the correct location and passes the results back."""

import logging
import os
import tempfile
import time
import traceback
from logging.handlers import RotatingFileHandler, SMTPHandler

import simplejson as json
from flask import Flask, request, Response, jsonify, url_for, redirect, send_file
from flask_mail import Mail
from pybmrb import csviz
from pythonjsonlogger import jsonlogger

from bmrbapi.exceptions import RequestException, ServerException
from bmrbapi.uniprot_mapper import map_uniprot, UniProtValidator
from bmrbapi.utils import querymod
from bmrbapi.utils.configuration import configuration
from bmrbapi.views.db_links import db_endpoints
from bmrbapi.views.molprobity import molprobity_endpoints
from bmrbapi.views.search import user_endpoints

# Set up the flask application
application = Flask(__name__)
# application.url_map.strict_slashes = False
application.register_blueprint(user_endpoints)
application.register_blueprint(molprobity_endpoints)
application.register_blueprint(db_endpoints)

# Set debug if running from command line
if application.debug:
    from flask_cors import CORS

    configuration['debug'] = True
    CORS(application)

# Set up paths for imports and such
local_dir = os.path.dirname(__file__)

# Set up the logging

# First figure out where to log
request_log_file = os.path.join(local_dir, "logs", "requests.log")
application_log_file = os.path.join(local_dir, "logs", "application.log")
request_json_file = os.path.join(local_dir, "logs", "json_requests.log")
if querymod.configuration.get('log'):
    if configuration['log'].get('json'):
        request_json_file = configuration['log']['json']
    if configuration['log'].get('request'):
        request_log_file = configuration['log']['request']
    if configuration['log'].get('application'):
        application_log_file = configuration['log']['application']

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
        and configuration['smtp'].get('server')
        and configuration['smtp'].get('admins')):

    # Don't send error e-mails in debugging mode
    if not configuration['debug']:
        mail_handler = SMTPHandler(mailhost=configuration['smtp']['server'],
                                   fromaddr='apierror@webapi.bmrb.wisc.edu',
                                   toaddrs=configuration['smtp']['admins'],
                                   subject='BMRB API Error occurred')
        mail_handler.setLevel(logging.WARNING)
        application.logger.addHandler(mail_handler)

    # Set up the mail interface
    application.config.update(
        MAIL_SERVER=configuration['smtp']['server'],
        # TODO: Make this configurable
        MAIL_DEFAULT_SENDER='noreply@bmrb.wisc.edu'
    )
    mail = Mail(application)
else:
    logging.warning("Could not set up SMTP logger because the configuration"
                    " was not specified.")


# Set up error handling
@application.errorhandler(ServerException)
@application.errorhandler(RequestException)
def handle_our_errors(exception):
    """ Handles exceptions we raised ourselves. """

    application.logger.info("Handled error raised in %s: %s", request.url, exception.message)
    return exception.to_response()


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

    if application.debug:
        raise error
    else:
        # Note! Returning the result of to_response() rather than raising the exception
        return ServerException("Server error. Contact bmrbhelp@bmrb.wisc.edu.").to_response()


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
                  "local": querymod.check_local_ip(), "time": time.time()})

    # Don't pretty-print JSON unless local user and in debug mode
    if request.args.get("pretty_print") == "true":
        application.config['JSONIFY_PRETTYPRINT_REGULAR'] = True


@application.route('/favicon.ico')
def favicon():
    """ Return the favicon. """

    return redirect(url_for('static', filename='favicon.ico'))


# Show what routes are available, determined programmatically
@application.route('/')
def catch_all():
    links = []
    for rule in sorted(application.url_map.iter_rules(), key=lambda x: str(x)):
        # Don't show the static endpoint
        if rule.endpoint in ['static', 'favicon'] or 'internal' in rule.endpoint:
            continue

        url = url_for(rule.endpoint, **{argument: argument.upper() for argument in rule.arguments})
        if not url:
            continue
        if "GET" in rule.methods:
            links.append("GET:  <a href='%s'>%s</a>" % (url, url))
        elif "POST" in rule.methods:
            links.append("POST: %s" % url)
        elif "PUT" in rule.methods:
            links.append("POST: %s" % url)
    return "<pre>" + "\n".join(links) + "</pre>"


@application.route('/refresh/uniprot')
def refresh_uniprot_internal():
    """ Refresh the UniProt links. """

    map_uniprot()
    return jsonify(True)


@application.route('/list_entries')
def list_entries():
    """ Return a list of all valid BMRB entries."""

    valid_list = ['metabolomics', 'macromolecules', 'chemcomps', 'combined']
    entries = querymod.list_entries(database=querymod.get_db("combined",
                                                             valid_list=valid_list))
    return jsonify(entries)


@application.route('/entry/', methods=['POST'])
@application.route('/entry/<entry_id>', methods=['GET'])
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
            # They are trying to send an entry using GET
            if request.args.get('data', None):
                raise RequestException("Cannot access this page through GET.")
            # They didn't specify an entry ID
            else:
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


@application.route('/schema/<schema_version>')
def return_schema(schema_version=None):
    """ Returns the BMRB schema as JSON. """
    return jsonify(querymod.get_schema(schema_version))


@application.route('/enumerations/<tag_name>')
def get_enumerations(tag_name=None):
    """ Returns all enumerations for a given tag."""

    return jsonify(querymod.get_enumerations(tag=tag_name,
                                             term=request.args.get('term')))


@application.route('/select', methods=['POST'])
def select():
    """ Performs an advanced select query. """

    data = json.loads(request.get_data(cache=False, as_text=True))
    return jsonify(querymod.process_select(**data))


@application.route('/software')
def get_software_summary():
    """ Returns a summary of all software used in all entries. """

    return jsonify(querymod.get_software_summary())


# Software queries
@application.route('/entry/<entry_id>/software')
def get_software_by_entry(entry_id=None):
    """ Returns the software used on a per-entry basis. """

    if not entry_id:
        raise RequestException("You must specify the entry ID.")

    return jsonify(querymod.get_entry_software(entry_id))


@application.route('/software/package/<package_name>')
def get_software_by_package(package_name=None):
    """ Returns the entries that used a particular software package. Search
    is done case-insensitive and is an x in y search rather than x == y
    search. """

    if not package_name:
        raise RequestException("You must specify the software package name.")

    return jsonify(querymod.get_software_entries(package_name,
                                                 database=querymod.get_db('macromolecules')))


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


@application.route('/entry/<entry_id>/simulate_hsqc')
def simulate_hsqc(entry_id):
    """ Returns the html for a simulated HSQC spectrum. """

    csviz._AUTOOPEN = False
    csviz._OPACITY = 1
    with tempfile.NamedTemporaryFile(suffix='.html') as output_file:
        csviz.Spectra().n15hsqc(entry_id, outfilename=output_file.name)

        return send_file(output_file.name)


@application.route('/instant')
def get_instant():
    """ Do the instant search. """

    if not request.args.get('term', None):
        raise RequestException("You must specify the search term using ?term=search_term")

    return jsonify(querymod.get_instant_search(term=request.args.get('term'),
                                               database=querymod.get_db('combined')))


@application.route('/status')
def get_status():
    """ Returns the server status."""

    return jsonify(querymod.get_status())


# Queries that run commands
@application.route('/entry/<entry_id>/validate')
def validate_entry(entry_id):
    """ Returns the validation report for the given entry. """

    return jsonify(querymod.get_chemical_shift_validation(ids=entry_id))
