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

"""Base archiver for SIPs.

The base archiver implements a basic API that allows subclasses to not having
to worry about e.g. files to disk.
"""

from __future__ import absolute_import, print_function, unicode_literals

import os
from hashlib import md5

from flask import current_app
from invenio_files_rest.models import FileInstance
from six import BytesIO

from .. import current_sipstore
from ..models import SIPMetadata
from ..signals import sipstore_archiver_status


class BaseArchiver(object):
    """Base archiver.

    The archiving is done in two steps:

    1. Generation of a list containing file information which contains all
       relevant information for writing down each file.
    2. Actual IO operation on the storage, which takes the previously generated
       list as input and writes it down to disk.

    The first step contains all archiver specific information on the archive
    structure and all relevant archive metadata that is to be written in
    addition to the "core" files, which are
    :py:class:`~invenio_sipstore.models.SIPFile` and
    :py:class:`~invenio_sipstore.models.SIPMetadata` files.

    The first step does not produce any side effects to the system. Specific
    archivers which inherit from this class are expected to primarily overwrite
    the :py:data:`BaseArchiver.get_all_files()` method to implement the,
    archiver-specific structure and any additional archived files.

    Relevant public method:

    * :py:data:`BaseArchiver.get_all_files()`

    Relevant protected methods:

    * :py:data:`BaseArchiver._get_data_files()`
    * :py:data:`BaseArchiver._get_metadata_files()`
    * :py:data:`BaseArchiver._get_extra_files()`

    The second step writes down the generated file information to disk using
    the configured storage class. By default it uses the file storage factory
    specified in
    :py:data:`~invenio_sipstore.config.SIPSTORE_FILE_STORAGE_FACTORY`
    configuration variable. This behaviour is overwritable by
    ``storage_factory`` parameter that can be provided to the constructor of
    this class.

    Relevant public method:

    * :py:data:`BaseArchiver.write_all_files()`

    Relevant protected methods:

    * :py:data:`BaseArchiver._write_sipfile()`
    * :py:data:`BaseArchiver._write_sipmetadata()`
    * :py:data:`BaseArchiver._write_extra()`
    """

    def __init__(self, sip, data_dir='files', metadata_dir='metadata',
                 extra_dir='', storage_factory=None,
                 filenames_mapping_file=None):
        """Base archiver constructor.

        :param sip: the SIP to archive.
        :type sip: :py:class:`invenio_sipstore.api.SIP`
        :param data_dir: Subdirectory in archive where the SIPFiles
            will be written.
        :param metadata_dir: Subdirectory in archive where the SIPMetadata
            files will be written.
        :param extra_dir: Subdirectory where all any extra files, that are
            specific to an archive standard, should be written.
        :param storage_factory: Storage factory used to create a new storage
            class instance.
        :param filenames_mapping_file: Mapping of file names.
        """
        self.sip = sip
        self.data_dir = data_dir
        self.metadata_dir = metadata_dir
        self.extra_dir = extra_dir
        self.storage_factory = storage_factory or \
            current_sipstore.storage_factory
        self.filenames_mapping_file = filenames_mapping_file

    def _get_archive_base_uri(self):
        """Get the base URI (absolute path) for the archive location.

        To configure the URI, specify the relevant configuration variable
        :py:data:`~invenio_sipstore.config.SIPSTORE_ARCHIVER_LOCATION_NAME`,
        with the name of the :py:class:`~invenio_files_rest.models.Location`
        object which will be used as the archive base URI.

        Returns the absolute path to the archive location, e.g.:

        * ``/data/archive/``
        * ``root://eospublic.cern.ch//eos/archive``
        """
        return current_sipstore.archive_location

    def _get_archive_subpath(self):
        """Generate the relative directory path of the archived SIP.

        The behaviour of this method can be changed by changing the
        :py:data:`~invenio_sipstore.config.SIPSTORE_ARCHIVER_DIRECTORY_BUILDER`
        configuration variable.

        Generates the relative directory path for the archived SIP, which
        should be unique for given SIP and is usually built from the SIP
        information and/or its assigned objects, e.g.:

        * ``/ab/cd/ab12-abcd-1234-dcba-123412341234`` (3-level chunk of SIP
          UUID identifier).
        * ``/12345/r/5`` (/<PID value>/r/<record revision id>)

        The return value of this method is a location that is *relative*
        to the base archive URI, the full path that is constructed later
        can be (based on examples from
        :py:data:`BaseArchiver._get_archive_base_uri()`):

        * ``/data/archive/ab/cd/ab12-abcd-1234-dcba-123412341234``
        * ``root://eospublic.cern.ch//eos/archive/12345/r/5``
        """
        return os.path.join(*current_sipstore.archive_path_builder(self.sip))

    def _get_fullpath(self, filepath):
        """Generate the absolute (full path) to the file in the archive system.

        :param filepath: path to the file, relative to archive subdirectory
            e.g. ``data/myfile.dat``.
        :type filepath: str
        :return: Absolute path, e.g.
            ``root://eospublic.cern.ch//eos/archive/12345/data/myfile.dat``
        :rtype: str
        """
        return os.path.join(
            self._get_archive_base_uri(),
            self._get_archive_subpath(),
            filepath
        )

    def _generate_sipfile_info(self, sipfile):
        """Generate the file information dictionary from a SIP file."""
        filename = current_sipstore.sipfile_name_formatter(sipfile)
        filepath = os.path.join(self.data_dir, filename)
        return dict(
            checksum=sipfile.checksum,
            size=sipfile.size,
            filepath=filepath,
            fullpath=self._get_fullpath(filepath),
            file_uuid=str(sipfile.file_id),
            filename=filename,
            sipfilepath=sipfile.filepath,
        )

    def _generate_sipmetadata_info(self, sipmetadata):
        """Generate the file information dictionary from a SIP metadata."""
        filename = current_sipstore.sipmetadata_name_formatter(sipmetadata)
        filepath = os.path.join(self.metadata_dir, filename)
        return dict(
            checksum='md5:{}'.format(str(
                md5(sipmetadata.content.encode('utf-8')).hexdigest())),
            size=len(sipmetadata.content),
            filepath=filepath,
            fullpath=self._get_fullpath(filepath),
            metadata_id=sipmetadata.type_id,
        )

    def _generate_extra_info(self, content, filename):
        """Generate the file information dictionary from a raw content."""
        filepath = os.path.join(self.extra_dir, filename)
        return dict(
            checksum='md5:{}'.format(
                    str(md5(content.encode('utf-8')).hexdigest())),
            size=len(content),
            filepath=filepath,
            fullpath=self._get_fullpath(filepath),
            content=content
        )

    def _get_sipfile_filename_mapping(self, filesinfo):
        """Generate filename mapping for SIPFiles.

        Due to archive file system specific issues, security reasons and
        archive package portability reasons, one might want to write down
        the SIP file under a different name than the one that was provided
        in the system (often by the user). In that case it is important to
        generate a mapping file between the original
        :py:data:`invenio_sipstore.models.SIPFile.filepath` entries and the
        archived filenames. It is important to include this mapping in the
        archive if ``SIPSTORE_ARCHIVER_SIPFILE_NAME_FORMATTER`` was set to
        anything other than the default formatter.

        See ``default_sipfile_name_formatter()`` and
        ``secure_sipfile_name_formatter()``.
        """
        content = '\n'.join('{0} {1}'.format(f['filename'],
                                             f['sipfilepath'])
                            for f in filesinfo)
        return self._generate_extra_info(content, self.filenames_mapping_file)

    def _get_data_files(self):
        """Get the file information for all the data files.

        The structure is defined by the JSON Schema
        ``sipstore/file-v1.0.0.json``.

        :return: list of dict containing file information.
        """
        files = []
        for f in self.sip.files:
            files.append(self._generate_sipfile_info(f))
        return files

    def _get_metadata_files(self):
        """Get the file information for the metadata files.

        The structure is defined by the JSON Schema
        ``sipstore/file-v1.0.0.json``.

        :return: list of dict containing file information.
        """
        # Consider only the explicitly-configured metadata types
        m_names = current_app.config['SIPSTORE_ARCHIVER_METADATA_TYPES']
        files = []
        for m in self.sip.metadata:
            if m.type.name in m_names:
                files.append(self._generate_sipmetadata_info(m))
        return files

    def _get_extra_files(self, data_files, metadata_files):
        """Get file information on any additional files in the archive.

        Return any additional files that are to be written. If
        ``filenames_mapping_file`` was set in the constructor, this method will
        generate a file containing the SIP filenames mapping.

        The structure is defined by the JSON Schema
        ``sipstore/file-v1.0.0.json``.

        :param data_files: File information on the SIP files.
        :param metadata_files: File information on the SIP metadata files
        :return: list of dict containing any additional files information.
        """
        ret = []
        if self.filenames_mapping_file and data_files:
            ret = [self._get_sipfile_filename_mapping(data_files), ]
        return ret

    def get_all_files(self):
        """Get the complete list of files in the archive.

        :return: the list of all relative final path
        """
        data_files = self._get_data_files()
        metadata_files = self._get_metadata_files()
        extra_files = self._get_extra_files(data_files, metadata_files)
        return data_files + metadata_files + extra_files

    def _write_sipfile(self, fileinfo=None, sipfile=None):
        """Write a SIP file to disk.

        ***Requires** either `fileinfo` or `sipfile` to be passed.

        Parameter `fileinfo` with the file information
        ('file_uuid' key required) or `sipfile` - the
        :py:data:`~invenio_sipstore.models.SIPFile` instance, in which case the
        relevant file information will be generated on the spot.

        :param fileinfo: File information on the SIPFile that is to be written.
        :type fileinfo: dict
        :param sipfile: SIP file to be written.
        :type sipfile: ``invenio_sipstore.models.SIPFile``
        """
        assert fileinfo or sipfile
        if not fileinfo:
            fileinfo = self._generate_sipfile_info(sipfile)
        if sipfile:
            fi = sipfile.file
        else:
            fi = FileInstance.query.get(fileinfo['file_uuid'])
        sf = self.storage_factory(fileurl=fileinfo['fullpath'],
                                  size=fileinfo['size'],
                                  modified=fi.updated)
        return sf.copy(fi.storage())

    def _write_extra(self, fileinfo=None, content=None, filename=None):
        """Write any extra file to the archive.

        *Requires EITHER `fileinfo` or (`content` AND `filename`).*

        :param fileinfo: File information on the custom file.
        :type fileinfo: dict
        :param content: Text content of the file
        :type content: str
        :param filename: Filename of the file.
        :type filename: str
        """
        assert fileinfo or (content and filename)
        if not fileinfo:
            fileinfo = self._generate_extra_info(content, filename)
        sf = self.storage_factory(fileurl=fileinfo['fullpath'],
                                  size=fileinfo['size'])
        return sf.save(BytesIO(fileinfo['content'].encode('utf-8')))

    def _write_sipmetadata(self, fileinfo=None, sipmetadata=None):
        """Write SIPMetadata file to disk."""
        assert fileinfo or sipmetadata
        if not fileinfo:
            fileinfo = self._generate_sipmetadata_info(sipmetadata)
        if not sipmetadata:
            sipmetadata = SIPMetadata.query.get(
                (self.sip.id, fileinfo['metadata_id']))
        sf = self.storage_factory(fileurl=fileinfo['fullpath'],
                                  size=fileinfo['size'],
                                  modified=sipmetadata.updated)
        return sf.save(BytesIO(sipmetadata.content.encode('utf-8')))

    def write_all_files(self, filesinfo=None):
        """Write all files to the archive.

        The only parameter of this method `filesinfo` is a list of dict,
        each containing information on the files that are to be written.
        There are three types of file-information dict that are recognizable:

        * SIPFile-originated, which copy the related FileInstance bytes.
        * SIPMetadata-originated, which write down the content of the metadata
          to the archive.
        * Extra files, which writes down short text files,
          that are usually specific to the archiver format, e.g.:
          manifest file, README, archive creation timestamp, etc.

        By the default when 'filesinfo' is omitted, the base archiver
        will generate the file info for all attached SIPFiles and SIPMetadata
        files (but only those which SIPMetadata.type.name was specified in the
        `SIPSTORE_ARCHIVER_METADATA_TYPES`). Specific archivers are expected
        to overwrite the `self.get_all_files` method, or craft the
        `filesinfo` parameter of this method externally.

        For more information on the structure of the file-info dict, see
        JSON Schema: invenio_sipstore.jsonschemas.sipstore.file-v1.0.0.json.

        :param filesinfo: A list of dict, specifying the file information
            that is to be written down to the archive. If not specified,
            will execute the `self.get_all_files` to build the files list.
        """
        if not filesinfo:
            filesinfo = self.get_all_files()
        keys = ['file_uuid', 'metadata_id', 'content']
        if not all(any(k in fi for k in keys) for fi in filesinfo):
            raise ValueError(
                "Missing one of mandatory keys ({keys}) in one or more "
                "file-information entries: {filesinfo}".format(
                    keys=keys,
                    filesinfo=filesinfo))
        total_size = sum(fi['size'] for fi in filesinfo)
        copied_size = 0
        for idx, fi in enumerate(filesinfo, 1):
            if 'file_uuid' in fi:
                self._write_sipfile(fileinfo=fi)
            elif 'metadata_id' in fi:
                self._write_sipmetadata(fileinfo=fi)
            else:  # (if 'content' in fi)
                self._write_extra(fileinfo=fi)

            copied_size += fi['size']
            sipstore_archiver_status.send({
                'total_files': len(filesinfo),
                'total_size': total_size,
                'copied_files': idx,
                'copied_size': copied_size,
                'current_filename': fi['filepath'],
                'current_filesize': fi['size']
            })
