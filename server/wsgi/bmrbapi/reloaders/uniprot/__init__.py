import logging

#
# The UniProt reloader that used to be here -- building web.uniprot_mappings
# and the web.hupo_psi_id materialized view -- now lives in the dbloader
# repository, in `loader/uniprot.py`, run by the web stage of the reload:
#
#   ~/git/dictionary/dbloader/loader/uniprot.py
#   deployed at /projects/BMRB/software/dictionary-meta/dbloader/
#
# It moved for the reason sql/initialize.sql and the timedomain scan did. The
# reload builds `web` as web_new and swaps it in wholesale, so anything not
# built into web_new beforehand is dropped with the old schema: the first
# release that did that took uniprot_mappings with it, and the summary pages
# failed on the missing relation. This module wrote `web.` and
# `macromolecules.` by name, so it could not target the shadow schemas; and
# hupo_psi_id, a view over macromolecules tables, cannot outlive a swap that
# replaces them.
#
# The lookups were rewritten on the way (see 3c7dabe, which fixed them here
# first): PDB chains come from SIFTS' bulk file rather than RCSB's retired
# describeMol API, entry names and accessions from rest.uniprot.org, and IDs
# are replaced by the primary accession rather than the last secondary one.
# Nothing is cached across runs any more.
#


def uniprot() -> None:
    """Deprecated: the database reload does this now. Accepted and ignored.

    Kept, rather than removed along with the `--uniprot` option, so that a
    condor job or a hand-run passing --uniprot does not die on an
    unrecognized argument.
    """

    logging.warning('--uniprot is obsolete and does nothing. web.uniprot_mappings and '
                    'web.hupo_psi_id are now built by dbloader/loader/uniprot.py, inside the '
                    'database reload, so that they land on the shadow schema before the swap. '
                    'See the comment in bmrbapi/reloaders/uniprot/__init__.py.')
