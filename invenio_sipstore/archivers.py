# -*- coding: utf-8 -*-
#
# This file is part of Invenio.
# Copyright (C) 2016 CERN.
#
# Invenio is free software; you can redistribute it
# and/or modify it under the terms of the GNU General Public License as
# published by the Free Software Foundation; either version 2 of the
# License, or (at your option) any later version.
#
# Invenio is distributed in the hope that it will be
# useful, but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Invenio; if not, write to the
# Free Software Foundation, Inc., 59 Temple Place, Suite 330, Boston,
# MA 02111-1307, USA.
#
# In applying this license, CERN does not
# waive the privileges and immunities granted to it by virtue of its status
# as an Intergovernmental Organization or submit itself to any jurisdiction.

"""Archivers for SIP."""

from __future__ import absolute_import, print_function

import hashlib
from datetime import datetime

from fs.opener import opener
from fs.path import dirname, join
from fs.utils import copyfile
from six import b


def get_checksum(checksum, expected='md5'):
    """Return the checksum if the type is the expected."""
    checksum = checksum.split(':')
    if checksum[0] != expected or len(checksum) != 2:
        raise AttributeError('Checksum format is not correct.')
    else:
        return checksum[1]


class BagItArchiver(object):
    """"BagIt archiver for SIP files."""

    def __init__(self, fs, tags=None):
        """Constuctor."""
        self.fs = fs
        self.tags = tags or {}

    @staticmethod
    def get_default_archive_location(sip, basepath, archived_at):
        """Return the default location to archive a SIP."""
        return join(basepath, str(sip.id), archived_at.isoformat())

    def archive(self, sip, progress_callback):
        """Archive the SIP generating a BagIt file."""
        files = sip.sip_files
        files_info = self.copy_files(files,
                                     progress_callback=progress_callback)
        metadata_file = self.save_file(['data', 'metadata.json'], '')
        files_info[metadata_file['filename']] = metadata_file

        self.autogenerate_tags(files_info)

        manifest_file_info = self.create_manifest_file(files_info)
        bagit_file_info = self.create_bagit_file()
        baginfo_file_info = self.create_baginfo_file()

        self.create_tagmanifest([manifest_file_info,
                                 bagit_file_info,
                                 baginfo_file_info, ])

    def copy_files(self, files, progress_callback):
        """Copy the files inside the new storage."""
        result = {}

        total_size = sum([file.file.size for file in files])
        copied = 0

        for file in files:
            src_fs, path = opener.parse(file.file.uri)
            calculated_filename = join('data', 'files', file.filepath)
            self.create_directories(calculated_filename)
            copyfile(src_fs, path,
                     self.fs, calculated_filename)
            file_size = file.file.size
            result[calculated_filename] = {
                'size': file_size,
                'checksum': file.file.checksum,
            }
            copied += file_size
            progress_callback(file_size, total_size)
        return result

    def autogenerate_tags(self, files_info):
        """Generate the automatic tags."""
        self.tags['Bagging-Date'] = datetime.now().strftime(
            "%Y-%m-%d_%H:%M:%S:%f")
        self.tags['Payload-Oxum'] = '{0}.{1}'.format(
            sum([f['size'] for f in files_info.values()]), len(files_info))

    def create_manifest_file(self, files_info):
        """Create the manifest file spcifying the checksum of the files."""
        content_items = ('{0} {1}'.format(get_checksum(c['checksum']), f)
                         for f, c in files_info.items())
        content = '\n'.join(content_items)
        return self.save_file(['manifest-md5.txt'], content)

    def create_bagit_file(self):
        """Create the bagit file which specify the version and encoding."""
        content_items = [
            'BagIt-Version: 0.97',
            'Tag-File-Character-Encoding: UTF-8',
        ]
        content = '\n'.join(content_items)
        return self.save_file(['bagit.txt'], content)

    def create_baginfo_file(self):
        """Create the baginfo file using the tags."""
        content_items = ('{0}: {1}'.format(k, v)
                         for k, v in self.tags.items())
        content = '\n'.join(content_items)
        return self.save_file(['bag-info.txt'], content)

    def create_tagmanifest(self, files_info):
        """Create the tagmanifest file using the files info."""
        content_items = ('{0} {1}'.format(get_checksum(fileinfo['checksum']),
                                          fileinfo['filename'])
                         for fileinfo in filter(None, files_info))
        content = '\n'.join(content_items)
        return self.save_file(['tagmanifest-md5.txt'], content)

    def save_file(self, filename, content):
        """Save the content inside the file.

        ..warning::

           This method should be used only to write small files.

        """
        content = b(content)
        filename = join(filename[0], *filename[1:])
        self.create_directories(filename)

        with self.fs.open(filename, 'wb') as fp:
            fp.write(content)

        return {
            'filename': filename,
            'size': len(content),
            'checksum': 'md5:{0}'.format(hashlib.md5(content).hexdigest()),
        }

    def create_directories(self, filename):
        """Create all the intermediate directories."""
        calculated_dir = dirname(filename)
        if not self.fs.exists(calculated_dir):
            self.fs.makedir(calculated_dir, recursive=True)
