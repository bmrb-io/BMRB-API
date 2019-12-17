import zlib

import simplejson as json
from flask import Blueprint, request, jsonify

from bmrbapi.exceptions import RequestException
from bmrbapi.utils.connections import RedisConnection, PostgresConnection

dictionary_endpoints = Blueprint('dictionary', __name__)


@dictionary_endpoints.route('/enumerations/<tag_name>')
def get_enumerations(tag_name):
    """ Returns all enumerations for a given tag."""

    term = request.args.get('term')
    if not tag_name.startswith("_"):
        tag_name = "_" + tag_name

    with PostgresConnection() as cur:
        cur.execute('''
SELECT CASE
           WHEN it.itemenumclosedflg = 'Y' THEN 'enumerations'
           WHEN it.enumeratedflg = 'Y' THEN 'common'
           ELSE null END   AS type,
       array_agg(enum.val) AS values
FROM dict.adit_item_tbl AS it
         LEFT JOIN dict.enumerations AS enum ON enum.seq = it.dictionaryseq
WHERE originaltag=%s
GROUP BY it.itemenumclosedflg, it.enumeratedflg;''', [tag_name])
        p_res = cur.fetchone()
    if not p_res:
        raise RequestException("Invalid tag specified.")

    # Generate the result dictionary
    result = dict(p_res)

    # Be able to search through enumerations based on the term argument
    if term:
        new_result = []
        for val in result['values']:
            if val and val.startswith(term):
                new_result.append({"value": val, "label": val})
        return jsonify(new_result)

    return jsonify(result)


@dictionary_endpoints.route('/schema/<schema_version>')
def return_schema(schema_version):
    """ Returns the BMRB schema as JSON. """

    with RedisConnection() as r:
        if not schema_version:
            schema_version = r.get('schema_version')
        try:
            schema = json.loads(zlib.decompress(r.get("schema:%s" % schema_version)))
        except TypeError:
            raise RequestException("Invalid schema version.")

        return jsonify(schema)
