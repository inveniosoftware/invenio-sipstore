# -*- coding: utf-8 -*-
#
# This file is part of Invenio.
# Copyright (C) 2017 CERN.
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

"""Base Archiver class for SIP."""

from hashlib import md5

from fs.opener import opener
from fs.path import dirname, join
from fs.utils import copyfile
from six import b

from invenio_sipstore.signals import sipstore_archiver_status


class BaseArchiver(object):
    """Base Archiver class for SIP.

    You can either access the files from the archive via the different
    getters, or generate the archive in a given folder via the following
    methods:

    - :func:`invenio_sipstore.archivers.base_archiver.BaseArchiver.init`
    - :func:`invenio_sipstore.archivers.base_archiver.BaseArchiver.create`
    - :func:`invenio_sipstore.archivers.base_archiver.BaseArchiver.finalize`
    """

    def __init__(self, sip):
        """Constructor.

        :param sip: the SIP to archive
        :type sip: :py:class:`invenio_sipstore.api.SIP`
        """
        self.path = ""
        self.fs = None
        self.sip = sip

    def get_files(self):
        """Return all the files in the archive, but not the metadata.

        :return: a dict with final relative path as keys and current location
            in Invenio as value
        :rtype: dict
        """
        return {f.filepath: f.storage_location
                for f in self.sip.files}

    def get_metadata(self):
        """Return the metadata.

        :return: a dict with final relative path as keys and content as value.
        :rtype: dict
        """
        return {m.type.name + '.' + m.type.format: m.content
                for m in self.sip.metadata}

    def get_all_files(self):
        """Return the complete list of files in the archive.

        All the files + all the metadata + some other files specific to the
        archive type if necessary.

        :return: the list of all relative final path
        """
        return list(self.get_files()) + list(self.get_metadata())

    def init(self, fs, folder):
        """Initialize the creation of the archive.

        :param str fs: a filesystem where to create the archive.
        :param str folder: the folder to create where will be stored the SIP.
        """
        self.fs = fs
        self.path = folder
        self._create_directories(folder)

    def create(self, filesdir="", metadatadir="", sipfiles=None,
               dry_run=False):
        """Create the archive.

        :param str filesdir: directory to which the data files will be written.
        :param str metadatadir: directory to which the metadata files will be
            written.
        :param sipfiles: a list of SIPFile objects to write. By default
            it's all of the SIPFiles attached to the SIP.
        :returns: a list with the dictionaries consiting of 'filename', 'size',
            'checksum' and the 'path', which contains the absolute path on
            the filesystem to which the file was written. Files from SIPFiles
            contain also 'file_uuid' key, which is the UUID (primary key) of
            the related FileInstance object.
        """
        sipfiles = sipfiles or self.sip.files
        files_info = self._copy_files(sipfiles, filesdir, dry_run=dry_run)
        metadata = self.get_metadata()
        for filename, content in metadata.items():
            files_info.append(self._save_file(
                join(metadatadir, filename),
                content, dry_run=dry_run))
        return files_info

    def finalize(self):
        """Finalize the creation.

        Among others, it deletes the directory of the archive.
        """
        self.fs.removedir(self.path, recursive=True, force=True)
        self.path = ""

    def _create_directories(self, dirname):
        """Create all the intermediate directories.

        :param str dirname: the name of the directory to create
        """
        if not self.fs.exists(dirname):
            self.fs.makedir(dirname, recursive=True)

    def _copy_files(self, files, filesdir="", dry_run=False):
        """Copy the files inside the new storage.

        Takes care of adding self.path at the beginning.

        :param files: the list of files to copy
        :type files: list(:py:class:`invenio_sipstore.models.SIPFile`)
        :param str filesdir: the directory where to copy files
        :param bool dry_run: When True, the files will not be copied,
            and only the file information will be returned. No changes will be
            made to disk or the database.
        :returns: a list with the dictionaries consiting of 'filename', 'size',
            'checksum' and the 'path', which contains the absolute path on
            the filesystem to which the file was written. Files from SIPFiles
            contain also 'file_uuid' key, which is the UUID (primary key) of
            the related FileInstance object.
        :rtype: list(dict)
        """
        result = []

        total_size = sum([file.size for file in files])
        copied_size = 0

        for i, file in enumerate(files):
            src_fs, path = opener.parse(file.storage_location)
            filename = join(filesdir, file.filepath)
            calculated_filename = join(self.path, filename)
            if not dry_run:
                self._create_directories(dirname(calculated_filename))
                copyfile(src_fs, path, self.fs, calculated_filename)
            result.append({
                'filename': filename,
                'size': file.size,
                'checksum': file.checksum,
                'path': self.fs.getsyspath(calculated_filename),
                'file_uuid': str(file.file.id)
            })
            copied_size += file.size

            sipstore_archiver_status.send({
                'total_files': len(files),
                'total_size': total_size,
                'copied_files': i,
                'copied_size': copied_size,
                'current_filename': filename,
                'current_filesize': file.size
            })
        return result

    def _save_file(self, filename, content, dry_run=False):
        """Save the content inside the file.

        Takes care of adding self.path in the filename.

        :param str filename: the name of the file
        :param str content: the content of the file
        :param bool dry_run: When True, the files will not be copied,
            and only the file information will be returned. No changes will be
            made to disk or the database.
        :returns: a dictionary describing the saved file, containing 'filename'
            'size', 'checksum' and 'path' which contains the absolute path on
            the filesystem to which the file was written.
        :rtype: dict

        ..warning::

           This method should be used only to write small files.

        """
        content = b(content)
        filenamepath = join(self.path, filename)
        if not dry_run:
            self._create_directories(dirname(filenamepath))
            with self.fs.open(filenamepath, 'wb') as fp:
                fp.write(content)

        return {
            'filename': filename,
            'size': len(content),
            'checksum': 'md5:' + str(md5(content).hexdigest()),
            'path': self.fs.getsyspath(filenamepath)
        }
