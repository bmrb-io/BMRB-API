import logging
import zlib

import pynmrstar

from bmrbapi.utils import querymod


def one_entry(entry_name, entry_location, r_conn):
    """ Load an entry and add it to REDIS """

    if "chemcomp" in entry_name:
        try:
            ent = querymod.create_chemcomp_from_db(entry_name)
        except Exception as e:
            ent = None
            logging.exception("On %s: error: %s" % (entry_name, str(e)))

        if ent is not None:
            key = querymod.locate_entry(entry_name, r_conn)
            r_conn.set(key, zlib.compress(ent.get_json().encode()))
            logging.info("On %s: loaded" % entry_name)
            return entry_name
    else:
        try:
            ent = pynmrstar.Entry.from_file(entry_location)

            logging.info("On %s: loaded." % entry_name)
        except IOError:
            ent = None
            logging.info("On %s: no file." % entry_name)
        except Exception as e:
            ent = None
            logging.error("On %s: error: %s" % (entry_name, str(e)))

        if ent is not None:
            key = querymod.locate_entry(entry_name, r_conn)
            r_conn.set(key, zlib.compress(ent.get_json().encode()))
            return entry_name
