from flask import Blueprint, Response, request, jsonify

# Local modules
from bmrbapi.utils.querymod import get_postgres_connection, RequestError

# Set up the blueprint
db_endpoints = Blueprint('db_links', __name__)


@db_endpoints.route('/mappings/uniprot')
def uniprot_mappings():
    """ Returns a list of the search methods."""

    cur = get_postgres_connection()[1]
    cur.execute('''
SELECT DISTINCT(uniprot_id) FROM web.uniprot_mappings
    WHERE uniprot_id != ''
    ORDER BY uniprot_id''')
    return Response("\n".join(["%s %s" % (x[0], x[0]) for x in cur.fetchall()]),
                    mimetype='text/plain')


@db_endpoints.route('/protein/uniprot')
@db_endpoints.route('/protein/uniprot/<accession_id>')
def uniprot(accession_id=None):
    """ Returns either a list of objects, or just a single object,
        in the appropriate format.

        Formats allowed: json, hupo-psi-id

        If uniprot_id is None, return all objects. Otherwise return just the object for
        the protein with the given UniProt ID."""

    cur = get_postgres_connection(dictionary_cursor=True)[1]

    # Get the format
    response_format = request.args.get('format', 'json')
    if response_format not in ['json', 'hupo-psi-id']:
        raise RequestError("Invalid format type. Allowed options: 'json', 'hupo-psi-id'.")

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
            return jsonify(cur.fetchall()[0][0])
        return jsonify([x[0] for x in cur.fetchall()])
