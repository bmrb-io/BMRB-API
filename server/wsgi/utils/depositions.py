#!/usr/bin/env python

from __future__ import print_function

import os
import json

from git import Repo, NoSuchPathError
import querymod

import werkzeug.utils
import flask


class DepositionRepo:
    """ A class to interface with git repos for depositions.

    You *MUST* use the 'with' statement when using this class to ensure that
    changes are committed."""

    def __init__(self, uuid, initialize=False):
        self.repo = None
        self.uuid = uuid
        self.initialize = initialize
        self.entry_dir = None
        self.modified_files = []
        self._live_metadata = None
        self._original_metadata = None

    def __enter__(self):
        """ Get a session cookie to use for future requests. """

        self.entry_dir = os.path.join(querymod.configuration['repo_path'], str(self.uuid))
        try:
            if self.initialize:
                self.repo = Repo.init(self.entry_dir)
                self.repo.config_writer().set_value("user", "name", "BMRBDep").release()
                self.repo.config_writer().set_value("user", "email", "bmrbhelp@bmrb.wisc.edu").release()
                os.mkdir(os.path.join(self.entry_dir, 'data_files'))
            else:
                self.repo = Repo(self.entry_dir)
        except NoSuchPathError:
            raise querymod.RequestError("'%s' is not a valid deposition ID." % self.uuid,
                                        status_code=404)

        return self

    def __exit__(self, exc_type, exc_value, traceback):
        """ End the current session."""

        # If nothing changed the commit won't do anything
        self.commit("Repo closed with changed but without a manual commit... Potential software bug.")
        self.repo.close()
        self.repo.__del__()

    @property
    def metadata(self):
        """ Return the metadata dictionary. """

        if not self._live_metadata:
            self._live_metadata = json.loads(self.get_file('submission_info.json'))
            self._original_metadata = self._live_metadata.copy()
        return self._live_metadata

    def get_entry(self):
        """ Return the NMR-STAR entry for this entry. """

        entry_location = os.path.join(self.entry_dir, 'entry.str')
        return querymod.pynmrstar.Entry.from_file(entry_location)

    def write_entry(self, entry):
        """ Save an entry in the standard place. """

        try:
            self.metadata['last_ip'] = flask.request.environ['REMOTE_ADDR']
        except RuntimeError:
            pass
        self.write_file('entry.str', str(entry), root=True)

    def get_file(self, filename, raw_file=False, root=True):
        """ Returns the current version of a file from the repo. """

        filename = werkzeug.utils.secure_filename(filename)
        if not root:
            filename = os.path.join('data_files', filename)
        try:
            file_obj = open(os.path.join(self.entry_dir, filename), "r")
            if raw_file:
                return file_obj
            else:
                return file_obj.read()
        except IOError:
            raise querymod.RequestError('No file with that name saved for this entry.')

    def write_file(self, filename, data, root=False):
        """ Adds (or overwrites) a file to the repo. """

        try:
            self.metadata['last_ip'] = flask.request.environ['REMOTE_ADDR']
        except RuntimeError:
            pass

        filename = werkzeug.utils.secure_filename(filename)
        if not root:
            filename = os.path.join('data_files', filename)

        with open(os.path.join(self.entry_dir, filename), "wb") as fo:
            fo.write(data)
        self.modified_files.append(filename)

    def commit(self, message):
        """ Commits the changes to the repository with a message. """

        # Check if the metadata has changed
        if self._live_metadata != self._original_metadata:
            self.write_file('submission_info.json',
                            json.dumps(self._live_metadata, indent=2, sort_keys=True),
                            root=True)
            self._original_metadata = self._live_metadata.copy()

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
