import datetime
from typing import List, Tuple

from flask import Blueprint, jsonify, Response
from psycopg2.extras import DictCursor

from bmrbapi.utils.connections import PostgresConnection
from bmrbapi.views.sql.metadata import *

# Set up the blueprint
meta_endpoints = Blueprint('metadata', __name__)


@meta_endpoints.route('/meta/release_statistics')
def get_release_statistics() -> Response:
    """ Returns statistics about released entries. """

    results = {}

    def get_query_results(cursor: DictCursor, query: str) -> List[Tuple[int, int]]:
        cursor.execute(query, [])
        return cursor.fetchall()

    with PostgresConnection(ets=True) as cur:

        years_to_show = range(1995, datetime.datetime.now().year + 1)

        # Do the queries
        total_released_in_year = get_query_results(cur, released_in_year)
        original_released_in_year = get_query_results(cur, original_release_in_year)

        structure_total_released_in_year = get_query_results(cur, structure_total_in_year)
        structure_adit_nmr_released_in_year = get_query_results(cur, structure_aditnmr_in_year)
        structure_onedep_released_in_year = get_query_results(cur, structure_onedep_in_year)
        structure_bmrbdep_released_in_year = get_query_results(cur, structure_bmrbdep_in_year)

        nonstructure_total_released_in_year = get_query_results(cur, nonstructure_total_in_year)
        nonstructure_adit_nmr_released_in_year = get_query_results(cur, nonstructure_aditnmr_in_year)
        nonstructure_onedep_released_in_year = get_query_results(cur, nonstructure_onedep_in_year)
        nonstructure_bmrbdep_released_in_year = get_query_results(cur, nonstructure_bmrbdep_in_year)

        def lookup_year(res, search_year: int):
            """ Returns the number of entries for a year from a list. """
            for row in res:
                if row[0] == search_year:
                    return row[1]
            return 0

        # Use this do to the calculations
        total_released_by_year = 0
        original_released_by_year = 0
        structure_released_by_year = 0
        nonstructure_released_by_year = 0

        for year in years_to_show:
            total_released_by_year += lookup_year(total_released_in_year, year)
            original_released_by_year += lookup_year(original_released_in_year, year)

            structure_released_by_year += lookup_year(structure_total_released_in_year, year)
            nonstructure_released_by_year += lookup_year(nonstructure_total_released_in_year, year)

            results[year] = {
                'total_released_by_year': total_released_by_year,
                'original_released_by_year': original_released_by_year,
                'structure_released_by_year': structure_released_by_year,
                'nonstructure_released_by_year': nonstructure_released_by_year,
                'released_in_year': lookup_year(total_released_in_year, year),
                'original_release_in_year': lookup_year(original_released_in_year, year),
                'structure_release_in_year': {
                    'total': lookup_year(structure_total_released_in_year, year),
                    'adit-nmr': lookup_year(structure_adit_nmr_released_in_year, year),
                    'onedep': lookup_year(structure_onedep_released_in_year, year),
                    'bmrbdep': lookup_year(structure_bmrbdep_released_in_year, year)
                },
                'nonstructure_release_in_year': {
                    'total': lookup_year(nonstructure_total_released_in_year, year),
                    'adit-nmr': lookup_year(nonstructure_adit_nmr_released_in_year, year),
                    'onedep': lookup_year(nonstructure_onedep_released_in_year, year),
                    'bmrbdep': lookup_year(nonstructure_bmrbdep_released_in_year, year)
                },
            }

    return jsonify({'release_information': results})
