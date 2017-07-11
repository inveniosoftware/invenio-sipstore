# -*- coding: utf-8 -*-
#
# This file is part of Invenio.
# Copyright (C) 2016, 2017 CERN.
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

from datetime import datetime

from fs.path import join

from invenio_sipstore.archivers import BaseArchiver


class BagItArchiver(BaseArchiver):
    """BagIt archiver for SIP files."""

    def __init__(self, sip, tags=None):
        """Constuctor.

        :param dict tags: a dictionnary for the tags of the bagit
        """
        super(BagItArchiver, self).__init__(sip)
        self.tags = tags or {}

    # overrides BaseArchiver.get_all_files()
    def get_all_files(self):
        """Return the complete list of files in the archive.

        All the files + all the metadata + bagit information.

        :return: the list of all relative final path
        """
        files = super(BagItArchiver, self).get_all_files()
        return files + ['manifest-md5.txt', 'bagit.txt', 'bag-info.txt',
                        'tagmanifest-md5.txt']

    def create(self):
        """Archive the SIP generating a BagIt file.

        :returns: a dictionnary with the filenames as keys, and size and
            checksum as value
        :rtype: dict
        """
        files_info = super(BagItArchiver, self).create(
            filesdir=join('data', 'files'), metadatadir='data')

        self.autogenerate_tags(files_info)

        metadata_info = self._save_file(*self.get_manifest_file(files_info))
        metadata_info.update(self._save_file(*self.get_bagit_file()))
        metadata_info.update(self._save_file(*self.get_baginfo_file()))
        metadata_info.update(
            self._save_file(*self.get_tagmanifest(metadata_info)))

        files_info.update(metadata_info)
        return files_info

    def autogenerate_tags(self, files_info):
        """Generate the automatic tags."""
        self.tags['Bagging-Date'] = datetime.now().strftime(
            "%Y-%m-%d_%H:%M:%S:%f")
        self.tags['Payload-Oxum'] = '{0}.{1}'.format(
            sum([f['size'] for f in files_info.values()]), len(files_info))

    def get_manifest_file(self, files_info):
        """Create the manifest file spcifying the checksum of the files.

        :return: the name of the file and its content
        :rtype: tuple
        """
        content = ('{0} {1}'.format(self._get_checksum(c['checksum']), f)
                   for f, c in files_info.items())
        return 'manifest-md5.txt', '\n'.join(content)

    def get_bagit_file(self):
        """Create the bagit file which specify the version and encoding.

        :return: the name of the file and its content
        :rtype: tuple
        """
        content = 'BagIt-Version: 0.97\nTag-File-Character-Encoding: UTF-8'
        return 'bagit.txt', content

    def get_baginfo_file(self):
        """Create the baginfo file using the tags.

        :return: the name of the file and its content
        :rtype: tuple
        """
        content_items = ('{0}: {1}'.format(k, v)
                         for k, v in self.tags.items())
        content = '\n'.join(content_items)
        return 'bag-info.txt', content

    def get_tagmanifest(self, files_info):
        """Create the tagmanifest file using the files info.

        :return: the name of the file and its content
        :rtype: tuple
        """
        files_info.pop(None, None)
        name, content = self.get_manifest_file(files_info)
        return 'tagmanifest-md5.txt', content

    @staticmethod
    def _get_checksum(checksum, expected='md5'):
        """Return the checksum if the type is the expected."""
        checksum = checksum.split(':')
        if checksum[0] != expected or len(checksum) != 2:
            raise AttributeError('Checksum format is not correct.')
        else:
            return checksum[1]
