#!/usr/bin/env python

from __future__ import print_function

import os
import json

from git import Repo, NoSuchPathError
import querymod


class DepositionRepo:
    """ A class to interface with git repos for depositions. """

    def __init__(self, uuid, initialize=False):
        self.repo = None
        self.uuid = uuid
        self.initialize = initialize
        self.entry_dir = None
        self.modified_files = []

    def __enter__(self):
        """ Get a session cookie to use for future requests. """

        self.entry_dir = os.path.join(querymod.configuration['repo_path'], str(self.uuid))
        try:
            if self.initialize:
                self.repo = Repo.init(self.entry_dir)
                self.repo.config_writer().set_value("user", "name", "BMRBDep").release()
                self.repo.config_writer().set_value("user", "email", "bmrbhelp@bmrb.wisc.edu").release()
            else:
                self.repo = Repo(self.entry_dir)
        except NoSuchPathError:
            raise querymod.RequestError("'%s' is not a valid deposition ID." % self.uuid,
                                        status_code=404)

        return self

    def __exit__(self, exc_type, exc_value, traceback):
        """ End the current session."""

        if self.modified_files:
            self.commit("Repo closed without a commit... Potential software bug.")
        self.repo.close()

    def get_metadata(self):
        """ Return the metadata dictionary. """

        return json.loads(self.get_file('submission_info.json'))

    def write_metadata(self, metadata):
        """ Return the metadata dictionary. """

        self.write_file('submission_info.json', json.dumps(metadata, indent=2, sort_keys=True))

    def get_entry(self):
        """ Return the NMR-STAR entry for this entry. """

        entry_location = os.path.join(self.entry_dir, 'entry.str')
        return querymod.pynmrstar.Entry.from_file(entry_location)

    def write_entry(self, entry):
        """ Save an entry in the standard place. """

        self.write_file('entry.str', str(entry))

    def get_file(self, filename):
        """ Returns the current version of a file from the repo. """

        return open(os.path.join(self.entry_dir, filename), "r").read()

    def write_file(self, filename, data):
        """ Adds (or overwrites) a file to the repo. """

        with open(os.path.join(self.entry_dir, filename), "wb") as fo:
            fo.write(data)
        self.modified_files.append(filename)

    def commit(self, message):
        """ Commits the changes to the repository with a message. """

        # No recorded changes
        if not self.modified_files:
            return False

        # See if they wrote the same value to an existing file
        if not self.repo.untracked_files and not [item.a_path for item in self.repo.index.diff(None)]:
            return False

        # Add the changes, commit
        self.repo.index.add(self.modified_files)
        self.repo.index.commit(message)
        self.modified_files = []
        return True
