from flask import Blueprint, jsonify, redirect, url_for

from bmrbapi.reloaders.uniprot import uniprot
from bmrbapi.utils.decorators import require_local

internal_endpoints = Blueprint('internal', __name__)


@internal_endpoints.route('/favicon.ico')
def favicon_internal():
    """ Return the favicon. """

    return redirect(url_for('static', filename='favicon.ico'))


@internal_endpoints.route('/refresh/uniprot')
@require_local
def refresh_uniprot_internal():
    """ Refresh the UniProt links. """

    uniprot()
    return jsonify(True)
