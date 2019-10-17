# Requirements.txt
from flask import jsonify, request, Blueprint

# Local modules
from .utils.querymod import get_postgres_connection, configuration, RequestError

# Set up the blueprint
molprobity_endpoints = Blueprint('molprobity', __name__)


@molprobity_endpoints.route('/molprobity/')
@molprobity_endpoints.route('/molprobity/<pdb_id>')
@molprobity_endpoints.route('/molprobity/<pdb_id>/oneline')
def return_molprobity_oneline(pdb_id=None):
    """Returns the molprobity data for a PDB ID. """

    if not pdb_id:
        raise RequestError("You must specify the PDB ID.")

    return jsonify(get_molprobity_data(pdb_id))


@molprobity_endpoints.route('/molprobity/<pdb_id>/residue')
def return_molprobity_residue(pdb_id):
    """Returns the molprobity residue data for a PDB ID. """

    return jsonify(get_molprobity_data(pdb_id, residues=request.args.getlist('r')))


def get_molprobity_data(pdb_id, residues=None):
    """ Returns the molprobity data."""

    pdb_id = pdb_id.lower()
    cur = get_postgres_connection()[1]

    if residues is None:
        sql = '''SELECT * FROM molprobity.oneline where pdb = %s'''
        terms = [pdb_id]
    else:
        terms = [pdb_id]
        if not residues:
            sql = '''SELECT * FROM molprobity.residue where pdb = %s;'''
        else:
            sql = '''SELECT * FROM molprobity.residue where pdb = %s AND ('''
            for item in residues:
                sql += " pdb_residue_no = %s OR "
                terms.append(item)
            sql += " 1=2) ORDER BY model, pdb_residue_no"

    cur.execute(sql, terms)

    res = {"columns": [desc[0] for desc in cur.description], "data": cur.fetchall()}

    if configuration['debug']:
        res['debug'] = cur.query

    return res
