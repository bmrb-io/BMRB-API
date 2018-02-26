#!/usr/bin/python

import os
import csv
from shutil import copyfile

try:
    os.mkdir("schemas")
except OSError:
    pass
os.chdir("schemas")
os.system("svn checkout http://svn.bmrb.wisc.edu/svn/nmr-star-dictionary/bmrb_only_files/adit_input/")

for rev in range(163, 230):
    os.system("cd adit_input;svn update -r %s" % rev)
    a = csv.reader(open("adit_input/xlschem_ann.csv","rU"))
    a.next()
    a.next()
    a.next()
    version = a.next()[3]
    copyfile("adit_input/xlschem_ann.csv", "%s.csv" % version)

os.system("rm -rfv adit_input")