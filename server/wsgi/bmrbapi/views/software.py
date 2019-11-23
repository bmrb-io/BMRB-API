from flask import jsonify, Blueprint

from bmrbapi.exceptions import RequestException
from bmrbapi.utils import querymod

# Set up the blueprint
software_blueprint = Blueprint('software', __name__)


@software_blueprint.route('/software')
def get_software_summary():
    """ Returns a summary of all software used in all entries. """

    return jsonify(querymod.get_software_summary())


@software_blueprint.route('/software/package/<package_name>')
def get_software_by_package(package_name=None):
    """ Returns the entries that used a particular software package. Search
    is done case-insensitive and is an x in y search rather than x == y
    search. """

    if not package_name:
        raise RequestException("You must specify the software package name.")

    return jsonify(querymod.get_software_entries(package_name,
                                                 database=querymod.get_db('macromolecules')))