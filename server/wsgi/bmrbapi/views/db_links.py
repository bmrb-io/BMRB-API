from flask import Blueprint, Response, request, jsonify

import bmrbapi.views.sql.db_links as sql_statements
from bmrbapi.exceptions import RequestException
from bmrbapi.utils.connections import PostgresConnection

# Set up the blueprint
db_endpoints = Blueprint('db_links', __name__)


@db_endpoints.route('/mappings/uniprot/uniprot')
def uniprot_mappings():
    """ Returns a list of the UniProt->UniProt where there is a BMRB record
    for the protein."""

    with PostgresConnection() as cur:
        cur.execute('''
SELECT DISTINCT(uniprot_id) FROM web.uniprot_mappings
    ORDER BY uniprot_id''')
        return Response("\n".join(["%s %s" % (x[0], x[0]) for x in cur.fetchall()]),
                        mimetype='text/plain')


@db_endpoints.route('/mappings/uniprot/bmrb')
def uniprot_bmrb_map():
    """ Returns a list of the UniProt->BMRB mappings."""

    with PostgresConnection() as cur:
        cur.execute('''
SELECT uniprot_id, array_agg(bmrb_id) FROM web.uniprot_mappings
GROUP BY uniprot_id
    ORDER BY uniprot_id''')
        return Response("\n".join(["%s %s" % (x[0], ",".join(x[1])) for x in cur.fetchall()]),
                        mimetype='text/plain')


@db_endpoints.route('/mappings/bmrb/uniprot')
def bmrb_uniprot_map():
    """ Returns a list of the BMRB->UniProt mappings."""

    with PostgresConnection() as cur:
        cur.execute('''
SELECT bmrb_id, array_agg(uniprot_id) FROM web.uniprot_mappings
GROUP BY bmrb_id
    ORDER BY bmrb_id''')
        return Response("\n".join(["%s %s" % (x[0], ",".join(x[1])) for x in cur.fetchall()]),
                        mimetype='text/plain')


@db_endpoints.route('/mappings/pdb/bmrb')
def pdb_bmrb_map():
    """ Returns a list of the PDB->BMRB mappings."""

    match_type = request.args.get('match_type', 'exact')
    format_ = request.args.get('format', 'text')

    with PostgresConnection() as cur:
        cur.execute(sql_statements.pdb_bmrb_map_author, [match_type])
        if format_ == "text":
            return Response("\n".join([x['string'] for x in cur.fetchall()]), mimetype='text/plain')
        else:
            return jsonify([[x['pdb_id'], x['bmrb_ids']] for x in cur.fetchall()])


@db_endpoints.route('/mappings/bmrb/pdb')
def bmrb_pdb_map():
    """ Returns a list of the BMRB-PDB mappings."""

    match_type = request.args.get('match_type', 'exact')
    format_ = request.args.get('format', 'text')

    with PostgresConnection() as cur:
        cur.execute(sql_statements.bmrb_pdb_map_exact, [match_type])
        if format_ == "text":
            return Response("\n".join([x['string'] for x in cur.fetchall()]), mimetype='text/plain')
        else:
            return jsonify([dict(x['bmrb_id'], x['pdb_ids']) for x in cur.fetchall()])


@db_endpoints.route('/protein/uniprot')
@db_endpoints.route('/protein/uniprot/<accession_id>')
def uniprot(accession_id=None):
    """ Returns either a list of objects, or just a single object,
        in the appropriate format.

        Formats allowed: json, hupo-psi-id

        If uniprot_id is None, return all objects. Otherwise return just the object for
        the protein with the given UniProt ID."""

    with PostgresConnection() as cur:

        # Get the format
        # Note on hupo-psi-id: https://github.com/normandavey/HUPO-PSI-ID/tree/master/ELIXIR_biohackathon
        response_format = request.args.get('format', 'json')
        if response_format not in ['json', 'hupo-psi-id']:
            raise RequestException("Invalid format type. Allowed options: 'json', 'hupo-psi-id'.")

        # Deal with the optional condition
        where, sql, terms = '', '', []
        if accession_id:
            terms = [accession_id]
            where = ' WHERE uni.uniprot_id = %s'

        if response_format == 'json':
            sql = '''
SELECT bmrb_id    AS "Entry_ID",
       entity_id  AS "Entity_ID",
       link_type  AS "Link_Type",
       uniprot_id AS "Accession_code"
FROM web.uniprot_mappings AS uni''' + where

        elif response_format == 'hupo-psi-id':
            if accession_id:
                sql = '''
SELECT json_build_object('proteinIdentifier', 'uniprot:'||uniprot_id, 'proteinRegions',
             array_agg(json_build_object('source', source,
                                        'regionSequenceExperimental', "regionSequenceExperimental",
                                        'experimentType', "experimentType",
                                        'experimentReference', "experimentReference",
                                        'lastModified', "lastModified")))
FROM web.hupo_psi_id
WHERE uniprot_id = %s
GROUP BY uniprot_id;
    '''
            else:
                sql = '''
SELECT json_build_object('proteinIdentifier', 'uniprot:'||uniprot_id, 'proteinRegions',
             array_agg(json_build_object('source', source,
                                        'regionSequenceExperimental', "regionSequenceExperimental",
                                        'experimentType', "experimentType",
                                        'experimentReference', "experimentReference",
                                        'lastModified', "lastModified")))
FROM web.hupo_psi_id
GROUP BY uniprot_id;
    '''

        cur.execute(sql, terms)
        if response_format == 'json':
            return jsonify([dict(x) for x in cur.fetchall()])
        elif response_format == 'hupo-psi-id':
            if accession_id:
                result = cur.fetchall()
                if len(result) >= 1:
                    return jsonify(result[0][0])
                else:
                    return jsonify([])
            return jsonify([x[0] for x in cur.fetchall()])
