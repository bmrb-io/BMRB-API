import logging

#
# The time domain scan that used to be here -- walking each entry's
# timedomain_data directory and filling web.timedomain_data -- now lives in the
# dbloader repository, in `loader/webextras.py` (`load_timedomain`), with the
# table declared in `webschema.sql`:
#
#   ~/git/dictionary/dbloader/loader/webextras.py
#   deployed at /projects/BMRB/software/dictionary-meta/dbloader/
#
# It moved with webapi.sql (was sql/initialize.sql), which reads
# web.timedomain_data while building query_grid and instant_extra_search_terms.
# The two have to run in that order and inside the same schema swap, so
# splitting them across two repositories and two condor jobs was not an option.
#
# The port takes its entry list from the archive the loader just built rather
# than from Redis, so it can no longer scan a list that disagrees with what is
# actually in the database. The set-counting rules are unchanged, quirks
# included -- an archive beside a directory of the same name counts once, and a
# lone wrapper directory is descended into -- because they determine published
# numbers.
#
# Where the directories live is configurable there (`[web] timedomain_dir`),
# because this module's `macromolecule_entry_directory` and dbloader's
# `entrydir` did not agree on whether the entry subdirectory has a `clean`
# level. It reports how many entries it found, so a wrong pattern shows up as a
# warning rather than as an archive that appears to have no time domain data.
#


def timedomain() -> None:
    """Deprecated: the database reload does this now. Accepted and ignored.

    Kept, rather than removed along with the `--timedomain` option, so that a
    deployed condor job still passing --timedomain does not die on an
    unrecognized argument. Drop both once updater_dag no longer sends it.
    """

    logging.warning('--timedomain is obsolete and does nothing. The scan it used to run '
                    'is now load_timedomain() in dbloader/loader/webextras.py, run inside '
                    'the database reload so that web.timedomain_data is filled before '
                    'webapi.sql reads it and lands on the shadow schema before the swap. '
                    'See the comment in bmrbapi/reloaders/timedomain.py.')
