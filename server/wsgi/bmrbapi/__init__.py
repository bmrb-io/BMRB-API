#!/usr/bin/env python3

""" This code is used to provide the REST API interface. """

import logging
import os
import subprocess
import time
import traceback
from logging.handlers import RotatingFileHandler, SMTPHandler

from flask import Flask, request, jsonify, url_for
from flask_mail import Mail
from pythonjsonlogger import jsonlogger
from werkzeug.exceptions import NotFound

from bmrbapi.exceptions import RequestException, ServerException
from bmrbapi.schemas import validate_parameters
from bmrbapi.utils import querymod
from bmrbapi.utils.configuration import configuration
from bmrbapi.utils.connections import RedisConnection, PostgresConnection
from bmrbapi.views.db_links import db_endpoints
from bmrbapi.views.dictionary import dictionary_endpoints
from bmrbapi.views.entry import entry_endpoints
from bmrbapi.views.internal import internal_endpoints
from bmrbapi.views.molprobity import molprobity_endpoints
from bmrbapi.views.search import search_endpoints

# Set up the flask application
application = Flask(__name__)
application.register_blueprint(search_endpoints)
application.register_blueprint(molprobity_endpoints)
application.register_blueprint(db_endpoints)
application.register_blueprint(entry_endpoints)
application.register_blueprint(internal_endpoints)
application.register_blueprint(dictionary_endpoints)

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
        MAIL_DEFAULT_SENDER='noreply@bmrb.wisc.edu'
    )
    mail = Mail(application)
else:
    logging.warning("Could not set up SMTP logger because the configuration was not specified.")


# Set up error handling
@application.errorhandler(ServerException)
@application.errorhandler(RequestException)
def handle_our_errors(exception):
    """ Handles exceptions we raised ourselves. """

    application.logger.info("Handled error raised in %s: %s", request.url, exception.message)
    # Note! Returning the result of to_response() rather than raising the exception
    return exception.to_response()


@application.errorhandler(Exception)
def handle_other_errors(error):
    """ Catches any other exceptions and formats them. Only
    displays the actual error to local clients (to prevent disclosing
    issues that could be security vulnerabilities)."""

    if isinstance(error, NotFound):
        return RequestException('The requested URL was not found on the server. If you '
                                'entered the URL manually please check your spelling and try again.',
                                status_code=404).to_response()

    # They are trying to hack the server. We catch this mainly just so we aren't spammed with server
    #  error emails.
    if isinstance(error, ValueError) and "A string literal cannot contain NUL" in str(error):
        return RequestException("Invalid request. Requests cannot contain null characters.",
                                status_code=400).to_response()

    application.logger.critical("Unhandled exception raised on request %s %s\n\n%s",
                                request.method, request.url,
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

    try:
        user_agent = request.headers.get('User-Agent', '?').split()[0]
    except IndexError:
        user_agent = '?'

    rlogger.info("%s %s %s %s %s", request.remote_addr, request.method,
                 request.full_path,
                 user_agent,
                 request.headers.get('Application', 'unknown'))

    jlogger.info({"user-agent": request.headers.get('User-Agent'),
                  "method": request.method, "endpoint": request.endpoint,
                  "application": request.headers.get('Application'),
                  "path": request.full_path, "ip": request.remote_addr,
                  "local": querymod.check_local_ip(), "time": time.time()})

    # Run the custom validator on all requests
    validate_parameters()


# Show what routes are available, determined programmatically
@application.route('/')
def catch_all():
    links = []
    for rule in sorted(application.url_map.iter_rules(), key=lambda x: str(x)):
        # Don't show the static endpoint
        if rule.endpoint == 'static':
            continue
        if 'internal' in rule.endpoint and not configuration['debug']:
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


@application.route('/status')
def get_status():
    """ Returns the server status."""

    stats = {}
    for key in ['metabolomics', 'macromolecules', 'chemcomps', 'combined']:
        stats[key] = {}
        with RedisConnection() as r:
            for k, v in r.hgetall("%s:meta" % key).items():
                k = k.decode()
                v = v.decode()
                stats[key][k] = v
        for skey in stats[key]:
            if skey == "update_time":
                stats[key][skey] = float(stats[key][skey])
            else:
                stats[key][skey] = int(stats[key][skey])

    with PostgresConnection() as pg:
        for key in ['metabolomics', 'macromolecules']:
            sql = '''SELECT reltuples FROM pg_class WHERE oid = '%s."Atom_chem_shift"'::regclass;''' % key
            pg.execute(sql)
            stats[key]['num_chemical_shifts'] = int(pg.fetchone()[0])

    try:
        stats['version'] = subprocess.check_output(["git", "describe", "--abbrev=0"]).strip()
    except subprocess.CalledProcessError:
        with open(os.path.join(os.path.dirname(os.path.realpath(__file__)), 'version.txt'), 'r') as version_file:
            stats['version'] = version_file.read().strip()

    return jsonify(stats)
