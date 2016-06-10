#!/usr/bin/env python

# Standard imports
import os
import sys
import time
import unittest
import requests
import querymod

url = 'http://localhost'

# We will use this for our tests
class TestAPI(unittest.TestCase):

    def setUp(self):
        pass

    def test_redis_is_populated(self):
        """ Make sure that the entry lists are populated"""

        # metabolomics
        entries = requests.get(url + "/rest/list_entries/metabolomics").json()
        self.assertGreater(len(entries), 1000)
        # chemcomps
        entries = requests.get(url + "/rest/list_entries/chemcomps").json()
        self.assertGreater(len(entries), 21000)
        # macromolecules
        entries = requests.get(url + "/rest/list_entries/macromolecules").json()
        self.assertGreater(len(entries), 10000)

    def test_redis_is_up_to_date(self):
        """ Make sure the last update has been within one week """

        stats = requests.get(url + "/rest/status/").json()
        for key in ['metabolomics', 'macromolecules', 'chemcomps', 'combined']:
            self.assertLess(time.time() - stats[key]['update_time'], 604800)
            self.assertLess(time.time() - stats[key]['update_time'], 604800)
            self.assertLess(time.time() - stats[key]['update_time'], 604800)
            self.assertLess(time.time() - stats[key]['update_time'], 604800)

    def test_entries_in_redis(self):
        """ Make sure that one entry in each class is there and parses."""

        self.assertEqual(querymod.bmrb.entry.fromDatabase(15000),
                         querymod.bmrb.entry.fromFile("/share/subedit/entries/bmr15000/clean/bmr15000_3.str"))
        self.assertEqual(querymod.bmrb.entry.fromDatabase("bmse000894"),
                         querymod.bmrb.entry.fromFile("/share/subedit/metabolomics/bmse000894/bmse000894.str"))
        self.assertEqual(querymod.bmrb.entry.fromDatabase("chemcomp_0EY"),
                         querymod.create_chemcomp_from_db("chemcomp_0EY"))

    def test_chemical_shifts(self):
        """ Make sure the chemical shift fetching method is working."""

        shifts = requests.get(url + "/rest/chemical_shifts/HB3").json()['data']
        self.assertGreater(len(shifts), 440000)
        shifts = requests.get(url + "/rest/chemical_shifts/C8/metabolomics")
        shifts = shifts.json()['data']
        self.assertGreater(len(shifts), 850)

    def test_zzz_block(self):
        """ See if we get banned for making too many queries."""

        r = requests.get(url + "/rest/").status_code
        self.assertEquals(r, 200)

        for x in range(0,50):
            r = requests.get(url + "/rest/").status_code
        self.assertEquals(r, 403)

        # Make sure we are unbanned before the next test
        time.sleep(11)

# Allow unit testing from other modules
def start_tests():
    unittest.main(module=__name__, exit=False)

# Run unit tests if we are called directly
if __name__ == '__main__':
    print("Use querymod to run the tests.")
