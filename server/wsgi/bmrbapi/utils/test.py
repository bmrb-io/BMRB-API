#!/usr/bin/env python3

# Standard imports
import sys
import time
import unittest
import requests
import pynmrstar
import querymod

from io import StringIO

url = 'http://localhost'


# We will use this for our tests
class TestAPI(unittest.TestCase):

    def setUp(self):
        self.session = requests.Session()
        self.session.headers.update({"Application": "BMRB_API_TEST"})

    def test_redis_is_populated(self):
        """ Make sure that the entry lists are populated"""

        # metabolomics
        entries = self.session.get(url + "/list_entries?database=metabolomics").json()
        self.assertGreater(len(entries), 1000)
        # chemcomps
        entries = self.session.get(url + "/list_entries?database=chemcomps").json()
        self.assertGreater(len(entries), 21000)
        # macromolecules
        entries = self.session.get(url + "/list_entries?database=macromolecules").json()
        self.assertGreater(len(entries), 10000)

    def test_redis_is_up_to_date(self):
        """ Make sure the last update has been within one week """

        stats = self.session.get(url + "/status").json()
        for key in ['metabolomics', 'macromolecules', 'chemcomps', 'combined']:
            self.assertLess(time.time() - stats[key]['update_time'], 604800)
            self.assertLess(time.time() - stats[key]['update_time'], 604800)
            self.assertLess(time.time() - stats[key]['update_time'], 604800)
            self.assertLess(time.time() - stats[key]['update_time'], 604800)

    def test_entries_in_redis(self):
        """ Make sure that one entry in each class is there and parses."""

        self.assertEqual(pynmrstar.Entry.from_database(15000),
                         pynmrstar.Entry.from_file("/share/subedit/entries/bmr15000/clean/bmr15000_3.str"))
        self.assertEqual(pynmrstar.Entry.from_database("bmse000894"),
                         pynmrstar.Entry.from_file("/share/subedit/metabolomics/bmse000894/bmse000894.str"))
        self.assertEqual(pynmrstar.Entry.from_database("chemcomp_0EY"),
                         querymod.create_chemcomp_from_db("chemcomp_0EY"))

    def test_chemical_shifts(self):
        """ Make sure the chemical shift fetching method is working."""

        shifts_url = "/search/chemical_shifts?atom_id=HB3&shift=1.820&threshold=.001&database=macromolecules"
        shifts = self.session.get(url + shifts_url).json()['data']
        self.assertGreater(len(shifts), 1350)
        shifts = self.session.get(url + "/search/chemical_shifts?atom_id=C8&database=metabolomics")
        shifts = shifts.json()['data']
        self.assertGreater(len(shifts), 850)

    def test_enumerations(self):
        """ Test that the enumerations is working."""

        enums = self.session.get(url + "/enumerations/_Entry.Experimental_method").json()['values']
        self.assertEquals(enums, ["NMR", "Theoretical"])

    def test_store_entry(self):
        """ See if we can store an entry in the DB and then retrieve it."""

        star_test = str(pynmrstar.Entry.from_file("/share/subedit/entries/bmr15000/clean/bmr15000_3.str"))
        response = self.session.post(url + "/entry/", data=star_test).json()

        # Check the response key length
        self.assertEqual(len(response['entry_id']), 32)

        # See if we can fetch the entry
        response2 = self.session.get(url + "/entry/%s" % response['entry_id'],
                                     data=star_test).json()

        # Make sure the returned entry equals the submitted entry
        self.assertEquals(pynmrstar.Entry.from_json(response2[response['entry_id']]),
                          pynmrstar.Entry.from_string(star_test))

        # Delete the entry we uploaded
        querymod.get_redis_connection().delete(querymod.locate_entry(response['entry_id']))

    def test_create_chemcomp_from_db(self):
        """ See if our code to generate a chemcomp from the DB is working."""

        # Test a few chemcomps for good measure
        # TODO: DUD triggers suboptimal behavior in PyNMRSTAR due to newline
        #  on the end of some tags
        for key in ["SES"]:
            # The entry generated locally
            local = querymod.create_chemcomp_from_db(key)
            # These come out sorted from octopus, so we need to sort too
            local.get_loops_by_category('Chem_comp_descriptor')[0].sort_rows(["Descriptor", "Type"])
            del local.get_saveframes_by_category("chem_comp")[0]["Atom_nomenclature_source"]

            # The local entry has converted datatypes straight from postgres
            #  so make sure to convert datatypes for the loaded entry
            ligand_expo_ent = requests.get(
                "http://octopus.bmrb.wisc.edu/ligand-expo?what=print&print_entity=yes&print_chem_comp=yes&%s=Fetch" %
                key).text
            ligand_expo_ent = "data_chemcomp_%s\n" % key + ligand_expo_ent
            ligand_expo_ent = pynmrstar.Entry.from_string(ligand_expo_ent)

            self.assertEquals(local, ligand_expo_ent)


# Set up the tests
def run_test(conf_url=querymod.configuration.get('url', None)):
    """ Run the unit tests and make sure the server is online."""

    if conf_url is None:
        raise ValueError("Please create a local api_config.json file in the "
                         "root directory of the repository with 'url' defined "
                         "with the root URL of the server. (No /rest or "
                         "/jsonrpc should be present.) Or provide URL on "
                         "command line.")

    # Tell the test framework where to query
    global url
    url = conf_url
    results = StringIO()

    # Run the test
    demo_test = unittest.TestLoader().loadTestsFromTestCase(TestAPI)
    unittest.TextTestRunner(stream=results).run(demo_test)

    # See if the end of the results says it passed
    results.seek(results.tell() - 3)
    if results.read() == "OK\n":
        sys.exit(0)
    else:
        results.seek(0)
        print(results.read())
        sys.exit(1)


# If called on the command line run a test
if __name__ == '__main__':

    if len(sys.argv) > 1:
        run_test(conf_url=sys.argv[1])
    else:
        run_test()
