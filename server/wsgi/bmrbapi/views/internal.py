from flask import Blueprint, redirect, url_for

internal_endpoints = Blueprint('internal', __name__)


@internal_endpoints.route('/favicon.ico')
def favicon_internal():
    """ Return the favicon. """

    return redirect(url_for('static', filename='favicon.ico'))

