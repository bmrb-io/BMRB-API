from flask import Blueprint, Response, request, jsonify

import bmrbapi.views.sql.db_links as sql_statements
from bmrbapi.exceptions import RequestException
from bmrbapi.utils.connections import PostgresConnection

# Set up the blueprint
db_endpoints = Blueprint('db_links', __name__)


def mapping_helper(direction: str):
    """ Performs the SQL queries needed to do BMRB -> UniProt mapping. """

    match_type = request.args.get('match_type', 'exact')
    format_ = "text" if direction == "uniprot_uniprot" else request.args.get('format', 'json')

    statements = {'uniprot_bmrb': {'text': sql_statements.uniprot_bmrb_map_text,
                                   'json': sql_statements.uniprot_bmrb_map_json},
                  'bmrb_uniprot': {'text': sql_statements.bmrb_uniprot_map_text,
                                   'json': sql_statements.bmrb_uniprot_map_json},
                  'pdb_bmrb': {'text': sql_statements.pdb_bmrb_map_text,
                               'json': sql_statements.pdb_bmrb_map_json},
                  'bmrb_pdb': {'text': sql_statements.bmrb_pdb_map_text,
                               'json': sql_statements.bmrb_pdb_map_json},
                  'uniprot_uniprot': {'text': sql_statements.uniprot_uniprot_map}
                  }

    with PostgresConnection() as cur:
        if format_ == "text":
            cur.execute(statements[direction][format_], [match_type])
            return Response("\n".join([x['string'] for x in cur.fetchall()]), mimetype='text/plain')
        elif format_ == 'json':
            cur.execute(statements[direction][format_], [match_type])
            return jsonify([dict(x) for x in cur.fetchall()])


@db_endpoints.route('/mappings/uniprot/uniprot')
def uniprot_mappings_internal():
    """ Returns a list of the UniProt->UniProt where there is a BMRB record
    for the protein."""

    return mapping_helper('uniprot_uniprot')


@db_endpoints.route('/mappings/uniprot/bmrb')
def uniprot_bmrb_map():
    """ Returns a list of the UniProt->BMRB mappings."""

    return mapping_helper('uniprot_bmrb')


@db_endpoints.route('/mappings/bmrb/uniprot')
def bmrb_uniprot_map():
    """ Returns a list of the BMRB->UniProt mappings."""

    return mapping_helper('bmrb_uniprot')


@db_endpoints.route('/mappings/pdb/bmrb')
def pdb_bmrb_map():
    """ Returns a list of the PDB->BMRB mappings."""

    return mapping_helper('pdb_bmrb')


@db_endpoints.route('/mappings/bmrb/pdb')
def bmrb_pdb_map():
    """ Returns a list of the BMRB-PDB mappings."""

    return mapping_helper('bmrb_pdb')


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
