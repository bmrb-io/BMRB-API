#!/usr/bin/env python3

""" This code is used to provide the REST API interface. """
import logging
import os
import subprocess
import traceback
from logging.handlers import SMTPHandler

import simplejson
from flask import Flask, request, jsonify, url_for, render_template
from flask.json.provider import JSONProvider
from flask_mail import Mail
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
from bmrbapi.views.metadata import meta_endpoints
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
application.register_blueprint(meta_endpoints)

# Set debug if running from command line
if application.debug:
    from flask_cors import CORS

    configuration['debug'] = True
    CORS(application)

# Set up paths for imports and such
local_dir = os.path.dirname(__file__)

# Set up logging to stderr (captured by Docker)
application.logger.setLevel(logging.WARNING)

# Set up the SMTP handler
if (querymod.configuration.get('smtp')
        and configuration['smtp'].get('server')
        and configuration['smtp'].get('admins')):

    # Don't send error e-mails in debugging mode
    if not configuration['debug']:
        mail_handler = SMTPHandler(mailhost=configuration['smtp']['server'],
                                   fromaddr=configuration['smtp']['from_address'],
                                   toaddrs=configuration['smtp']['admins'],
                                   subject='BMRB API Error occurred')
        mail_handler.setLevel(logging.WARNING)
        application.logger.addHandler(mail_handler)

    # Set up the mail interface
    application.config.update(
        MAIL_SERVER=configuration['smtp']['server'],
        MAIL_DEFAULT_SENDER=configuration['smtp']['from_address']
    )
    mail = Mail(application)
else:
    logging.warning("Could not set up SMTP logger because the configuration was not specified.")


# We use this custom JSON provider, because otherwise Decimal objects are not properly converted
class SimpleJSONProvider(JSONProvider):
    def dumps(self, obj, *, option=None, **kwargs):
        return simplejson.dumps(obj)

    def loads(self, s, **kwargs):
        return simplejson.loads(s)


application.json = SimpleJSONProvider(application)


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
        return ServerException(f"Server error. Contact {configuration['smtp']['from_address']}.").to_response()


@application.before_request
def validate_request():
    """ Validate all requests. """
    validate_parameters()


@application.route('/robots.txt')
def robots_txt():
    """ Serves the robots.txt file. """
    return """
User-agent: *
Disallow: /current/entry/*/simulate_hsqc
Disallow: /v2/entry/*/simulate_hsqc
Disallow: /current/search/chemical_shifts
Disallow: /v2/search/chemical_shifts
""", 200, {'Content-Type': 'text/plain'}


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

    return render_template('base.html', content="\n".join(links))


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
            stats[key]['num_chemical_shifts'] = int(pg.fetchone()['reltuples'])

    try:
        stats['version'] = subprocess.check_output(["git", "describe", "--abbrev=0"], stderr=subprocess.DEVNULL).strip()
    except (subprocess.CalledProcessError, FileNotFoundError):
        with open(os.path.join(os.path.dirname(os.path.realpath(__file__)), 'version.txt'), 'r') as version_file:
            stats['version'] = version_file.read().strip()

    return jsonify(stats)
