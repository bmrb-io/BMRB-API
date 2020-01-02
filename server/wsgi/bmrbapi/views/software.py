from flask import jsonify, Blueprint

from bmrbapi.utils.connections import PostgresConnection
from bmrbapi.utils.querymod import get_db

software_blueprint = Blueprint('software', __name__)


@software_blueprint.route('/software')
def get_software_summary():
    """ Returns a summary of all software used in all entries. """

    with PostgresConnection(schema=get_db('macromolecules')) as cur:
        # Get the list of which tags should be used to order data
        cur.execute('''
SELECT "Software"."Name","Software"."Version",task."Task" AS "Task",vendor."Name" AS "Vendor Name"
FROM "Software"
  LEFT JOIN "Vendor" AS vendor
    ON "Software"."Entry_ID"=vendor."Entry_ID" AND "Software"."ID"=vendor."Software_ID"
  LEFT JOIN "Task" AS task
    ON "Software"."Entry_ID"=task."Entry_ID" AND "Software"."ID"=task."Software_ID";''')

        column_names = [desc[0] for desc in cur.description]
        return jsonify({"columns": column_names, "data": cur.fetchall()})


@software_blueprint.route('/software/package/<package_name>')
def get_software_by_package(package_name):
    """ Returns the entries that used a particular software package. Search
    is done case-insensitive and is an x in y search rather than x == y
    search. """

    with PostgresConnection(schema=get_db('macromolecules')) as cur:
        # Get the list of which tags should be used to order data
        cur.execute('''
SELECT "Software"."Entry_ID","Software"."Name","Software"."Version",vendor."Name" AS "Vendor Name",
  vendor."Electronic_address" AS "e-mail",task."Task" AS "Task"
FROM "Software"
  LEFT JOIN "Vendor" AS vendor
    ON "Software"."Entry_ID"=vendor."Entry_ID" AND "Software"."ID"=vendor."Software_ID"
  LEFT JOIN "Task" AS task
    ON "Software"."Entry_ID"=task."Entry_ID" AND "Software"."ID"=task."Software_ID"
WHERE lower("Software"."Name") LIKE lower(%s);''', ["%" + package_name + "%"])

        column_names = [desc[0] for desc in cur.description]
        return jsonify({"columns": column_names, "data": cur.fetchall()})
