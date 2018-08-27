#!/usr/bin/env python

from __future__ import print_function

import os
import json
import time
import random

from git import Repo, NoSuchPathError
import querymod

import werkzeug.utils
import flask


def secure_filename(filename):
    """ Wraps werkzeug secure_filename but raises an error if the filename comes out empty. """

    filename = werkzeug.utils.secure_filename(filename)
    if not filename:
        raise querymod.RequestError('Invalid upload file name. Please rename the file and try again.')
    return filename


class DepositionRepo:
    """ A class to interface with git repos for depositions.

    You *MUST* use the 'with' statement when using this class to ensure that
    changes are committed."""

    def __init__(self, uuid, initialize=False):
        self._repo = None
        self._uuid = uuid
        self._initialize = initialize
        self._entry_dir = None
        self._modified_files = False
        self._live_metadata = None
        self._original_metadata = None
        self._lock_path = os.path.join(querymod.configuration['repo_path'], str(uuid), '.git', 'api.lock')

    def __enter__(self):
        """ Get a session cookie to use for future requests. """

        self._entry_dir = os.path.join(querymod.configuration['repo_path'], str(self._uuid))
        try:
            if self._initialize:
                self._repo = Repo.init(self._entry_dir)
                with open(self._lock_path, "w") as f:
                    f.write(str(os.getpid()))
                self._repo.config_writer().set_value("user", "name", "BMRBDep").release()
                self._repo.config_writer().set_value("user", "email", "bmrbhelp@bmrb.wisc.edu").release()
                os.mkdir(os.path.join(self._entry_dir, 'data_files'))
            else:
                counter = 10
                while os.path.exists(self._lock_path):
                    counter -= 1
                    time.sleep(random.random())
                    if counter <= 0:
                        raise querymod.ServerError('Could not acquire entry directory lock.')
                with open(self._lock_path, "w") as f:
                    f.write(str(os.getpid()))
                self._repo = Repo(self._entry_dir)
        except NoSuchPathError:
            raise querymod.RequestError("'%s' is not a valid deposition ID." % self._uuid,
                                        status_code=404)

        return self

    def __exit__(self, exc_type, exc_value, traceback):
        """ End the current session."""

        # If nothing changed the commit won't do anything
        self.commit("Repo closed with changed but without a manual commit... Potential software bug.")
        self._repo.close()
        self._repo.__del__()
        os.unlink(self._lock_path)

    @property
    def metadata(self):
        """ Return the metadata dictionary. """

        if not self._live_metadata:
            self._live_metadata = json.loads(self.get_file('submission_info.json'))
            self._original_metadata = self._live_metadata.copy()
        return self._live_metadata

    def get_entry(self):
        """ Return the NMR-STAR entry for this entry. """

        entry_location = os.path.join(self._entry_dir, 'entry.str')
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

        filename = secure_filename(filename)
        if not root:
            filename = os.path.join('data_files', filename)
        try:
            file_obj = open(os.path.join(self._entry_dir, filename), "r")
            if raw_file:
                return file_obj
            else:
                return file_obj.read()
        except IOError:
            raise querymod.RequestError('No file with that name saved for this entry.')

    def get_data_file_list(self):
        """ Returns the list of data files associated with this deposition. """

        return os.listdir(os.path.join(self._entry_dir, 'data_files'))

    def delete_data_file(self, filename):
        """ Delete a data file by name."""

        filename = secure_filename(filename)
        os.unlink(os.path.join(self._entry_dir, 'data_files', filename))
        self._modified_files = True

    def write_file(self, filename, data, root=False):
        """ Adds (or overwrites) a file to the repo. """

        try:
            self.metadata['last_ip'] = flask.request.environ['REMOTE_ADDR']
        except RuntimeError:
            pass

        filename = secure_filename(filename)
        filepath = filename
        if not root:
            filepath = os.path.join('data_files', filename)

        with open(os.path.join(self._entry_dir, filepath), "wb") as fo:
            fo.write(data)
        self._modified_files = True

        return filename

    def commit(self, message):
        """ Commits the changes to the repository with a message. """

        # Check if the metadata has changed
        if self._live_metadata != self._original_metadata:
            self.write_file('submission_info.json',
                            json.dumps(self._live_metadata, indent=2, sort_keys=True),
                            root=True)
            self._original_metadata = self._live_metadata.copy()

        # No recorded changes
        if not self._modified_files:
            return False

        # See if they wrote the same value to an existing file
        if not self._repo.untracked_files and not [item.a_path for item in self._repo.index.diff(None)]:
            return False

        # Add the changes, commit
        self._repo.git.add(all=True)
        self._repo.git.commit(message=message)
        self._modified_files = False
        return True
