import logging

#
# The SQL this used to run -- sql/initialize.sql, building web.query_grid,
# web.chem_shifts, web.instant_cache, web.instant_extra_search_terms and
# web.metabolomics_summary -- now lives in the dbloader repository as
# `webapi.sql`, and is run by `loader/webextras.py` as the last step of the web
# stage:
#
#   ~/git/dictionary/dbloader/webapi.sql
#   deployed at /projects/BMRB/software/dictionary-meta/dbloader/webapi.sql
#
# It moved because it has to be inside the swap to be correct. Everything it
# builds sits on top of `macromolecules`, `metabolomics` and `web`, and the
# loader now rebuilds all three as <schema>_new and renames them into place in
# one transaction. Run afterwards, as this job did, it would spend its whole
# run rebuilding objects the swap had just destroyed -- the website missing the
# query grid and instant search until it finished.
#
# Editing it is otherwise unchanged: same file, same statements, and it is
# still plain SQL. Only where it lives and who runs it changed.
#


def sql_initialize(host=None, database=None, user=None) -> bool:
    """Deprecated: the database reload runs this now. Accepted and ignored.

    Kept, rather than removed along with the `--sql` option, so that a deployed
    condor job still passing --sql does not die on an unrecognized argument
    before the rest of the reloaders get to run. Drop both once updater_dag no
    longer sends it.
    """

    logging.warning('--sql is obsolete and does nothing. The SQL it used to run is now '
                    'dbloader/webapi.sql, run inside the database reload so that it lands '
                    'on the shadow schemas before the swap. See the comment in '
                    'bmrbapi/reloaders/sql_initialize.py.')
    return True
