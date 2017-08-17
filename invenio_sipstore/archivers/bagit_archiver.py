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

from __future__ import absolute_import, print_function, unicode_literals

import json
from datetime import datetime

from flask import current_app
from invenio_db import db
from jsonschema import validate

from invenio_sipstore.archivers import BaseArchiver
from invenio_sipstore.models import SIPMetadata, SIPMetadataType, \
    current_jsonschemas


class BagItArchiver(BaseArchiver):
    """BagIt archiver for SIPs.

    Archives the SIP in the BagIt archive format (v0.97). For more information
    on the BagIt standard visit: https://tools.ietf.org/html/draft-kunze-bagit
    """

    bagit_metadata_type_name = 'bagit'
    """Name of the SIPMetadataType for internal use of BagItArchiver."""

    archiver_version = 'SIPBagIt-v1.0.0'
    """Specification of the SIP bag structure.

    This name will be formatted as ``External-Identifier`` tag::

        External-Identifier: <SIP.id>/<archiver_version>
    """

    def __init__(self, sip, data_dir='data/files',
                 metadata_dir='data/metadata', extra_dir='', patch_of=None,
                 include_all_previous=False, tags=None,
                 filenames_mapping_file='data/filenames.txt'):
        """Constructor of the BagIt Archiver.

        When specifying 'patch_of' parameter the 'include_all_previous'
        flag determines whether files that are missing in the archived SIP
        (w.r.t. the SIP specified in 'patch_of') should be treated as
        explicitly deleted (include_all_previous=False) or if they
        should still be included in the manifest.

        Example:
            include_all_previous = True
              SIP_1:
                SIPFiles: a.txt, b.txt
                BagIt Manifest: a.txt, b.txt
              SIP_2 (Bagged with patch_of=SIP_1):
                SIPFiles: b.txt, c.txt
                BagIt Manifest: a.txt, b.txt, c.txt
                fetch.txt: a.txt, b.txt

            include_all_previous = False
              SIP_1:
                SIPFiles: a.txt, b.txt
                BagIt Manifest: a.txt, b.txt
              SIP_2 (Bagged with patch_of=SIP_1):
                SIPFIles: b.txt, c.txt
                BagIt Manifest: b.txt, c.txt
                fetch.txt: b.txt

        :param sip: API instance of the SIP that is to be archived.
        :type sip: invenio_sipstore.api.SIP
        :param data_dir: directory where the SIPFiles will be written.
        :param metadata_dir: directory where the SIPMetadata will be written.
        :param extra_dir: directory where all extra files will be written,
            including the BagIt-specific files.
        :param patch_of: Write a 'lightweight' bag, which will archive only
            the new SIPFiles, and refer to the repeated ones in "fetch.txt"
            file. The provided argument is a SIP API, which will be taken as a
            base for determining the "diff" between two bags.
        :type patch_of: invenio_sipstore.models.SIP or None
        :type bool include_missing_files: If set to True and if 'patch_of' is
            used, include the files that are missing in the SIP w.r.t. to
            the 'patch_of' SIP in the manifest.
            The opposite (include_missing_files=False) is equivalent to
            treating those as explicitly deleted - the files will not be
            included in the manifest, nor in the "fetch.txt" file.
        :param tags: a list of 2-tuple containing the tags of the bagit,
            which will be written to the 'bag-info.txt' file.
        :param filenames_mapping_file: filepath of the file in the archive
            which contains all of SIPFile mappings. If this parameter is
            boolean-resolvable as False, the file will not be created.
        """
        super(BagItArchiver, self).__init__(
            sip, data_dir=data_dir, metadata_dir=metadata_dir,
            extra_dir=extra_dir, filenames_mapping_file=filenames_mapping_file)
        self.tags = tags or current_app.config['SIPSTORE_BAGIT_TAGS']
        self.patch_of = patch_of
        self.include_all_previous = include_all_previous

    @staticmethod
    def _is_fetched(file_info):
        """Determine if file info specifies a file that is fetched."""
        return 'fetched' in file_info and file_info['fetched']

    @classmethod
    def _get_bagit_metadata_type(cls):
        """Return the SIPMetadataType for the BagIt metadata files."""
        return SIPMetadataType.get_from_name(cls.bagit_metadata_type_name)

    @classmethod
    def get_bagit_metadata(cls, sip, as_dict=False):
        """Fetch the BagIt metadata information (SIPMetadata).

        :param sip: SIP for which to fetch the metadata.

        :returns: Return the BagIt metadata information (SIPMetadata) instace
            or None if the object does not exist.
        """
        sm = SIPMetadata.query.filter_by(
            sip_id=sip.id,
            type_id=cls._get_bagit_metadata_type().id).one_or_none()
        if sm and as_dict:
            return json.loads(sm.content)
        else:
            return sm

    def get_bagit_file(self):
        """Create the bagit.txt file which specifies the version and encoding.

        :return: File information dictionary
        :rtype: dict
        """
        content = 'BagIt-Version: 0.97\nTag-File-Character-Encoding: UTF-8'
        return self._generate_extra_info(content, 'bagit.txt')

    def get_fetch_file(self, filesinfo):
        """Generate the contents of the fetch.txt file."""
        content = '\n'.join('{0} {1} {2}'.format(f['fullpath'], f['size'],
                                                 f['filepath'])
                            for f in filesinfo)
        return self._generate_extra_info(content, 'fetch.txt')

    def _generate_md5manifest_content(self, filesinfo):
        content = '\n'.join('{0} {1}'.format(self._get_checksum(
                   f['checksum']), f['filepath']) for f in filesinfo)
        return content

    def get_manifest_file(self, filesinfo):
        """Create the manifest file specifying the checksum of the files.

        :return: the name of the file and its content
        :rtype: tuple
        """
        content = self._generate_md5manifest_content(filesinfo)
        return self._generate_extra_info(content, 'manifest-md5.txt')

    def _generate_payload_oxum(self, filesinfo):
        return "{0}.{1}".format(
            sum([f['size'] for f in filesinfo]),
            len(filesinfo)
        )

    def _generate_bagging_date(self):
        """Generate the bagging date timestamp."""
        return datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S.%f")

    def get_baginfo_file(self, filesinfo):
        """Create the bag-info.txt file from the tags."""
        # Include some auto-generated tags
        content = []
        for t_name, t_value in self.tags:
            if t_name == 'Payload-Oxum':
                t_value = self._generate_payload_oxum(filesinfo)
            elif t_name == 'Bagging-Date':
                t_value = self._generate_bagging_date()
            elif t_name == 'External-Identifier' and t_value is None:
                t_value = '{0}/{1}'.format(self.sip.id, self.archiver_version)
            content.append("{0}: {1}".format(t_name, t_value))

        content = "\n".join(content)
        return self._generate_extra_info(content, 'bag-info.txt')

    def get_tagmanifest_file(self, filesinfo):
        """Create the tagmanifest file using the files info.

        :return: the name of the file and its content
        :rtype: tuple
        """
        content = self._generate_md5manifest_content(filesinfo)
        return self._generate_extra_info(content, 'tagmanifest-md5.txt')

    def get_all_files(self):
        """Create the BagIt metadata object."""
        data_files = self._get_data_files()
        if self.patch_of:
            prev_data_files = [fi for fi in self.get_bagit_metadata(
                self.patch_of, as_dict=True)['files'] if 'file_uuid' in fi]
            # We need to determine which files are to be fetched and
            # which need to be written down to the archive

            # Helper mapping of UUID-tu-Data-Fileinfo
            id2df = dict((fi['file_uuid'], fi) for fi in data_files)
            # Helper mapping of UUID-tu-Previous-Data-Fileinfo
            id2pdf = dict((fi['file_uuid'], fi) for fi in prev_data_files)

            # Create sets for easier set operations
            pdf_s = set(id2pdf.keys())
            df_s = set(id2df.keys())
            # If all previous files are included, simply assume that all
            # previous files are to be fetched (pdf_s), as it's the most
            # optimal solution, otherwise take the union of old and new files
            # only (pdf_s & df_s)
            if self.include_all_previous:
                fetched_uuids = pdf_s
            else:
                fetched_uuids = pdf_s & df_s

            # Archived (written to disk) files are then only the strictly
            # new files, i.e.: data files minus the previous data
            # files (df_s - pdf_s)
            archived_uuids = df_s - pdf_s

            data_files = []   # We will build the list of data files again
            for uuid in fetched_uuids:
                fi = id2pdf[uuid]
                # If the file is attached to the new SIP, use the new filepath
                fi['filepath'] = id2df[uuid]['filepath'] if uuid in id2df \
                    else fi['filepath']
                fi['fetched'] = True
                data_files.append(fi)
            for uuid in archived_uuids:
                data_files.append(id2df[uuid])

        metadata_files = self._get_metadata_files()
        extra_files = self._get_extra_files(data_files, metadata_files)

        bagit_files = []
        fetched_fi = [fi for fi in data_files if self._is_fetched(fi)]
        if fetched_fi:
            bagit_files.append(self.get_fetch_file(fetched_fi))
        bagit_files.append(self.get_baginfo_file(data_files + metadata_files +
                                                 extra_files))
        bagit_files.append(self.get_manifest_file(data_files + metadata_files +
                                                  extra_files))
        bagit_files.append(self.get_bagit_file())
        bagit_files.append(self.get_tagmanifest_file(bagit_files))

        return data_files + metadata_files + extra_files + bagit_files

    def save_bagit_metadata(self, filesinfo=None):
        """Generate and save the BagIt metadata information as SIPMetadata."""
        if not filesinfo:
            filesinfo = self.get_all_files()
        bagit_schema = current_jsonschemas.path_to_url(
            current_app.config['SIPSTORE_DEFAULT_BAGIT_JSONSCHEMA'])
        bagit_metadata = {
            'files': filesinfo,
            '$schema': bagit_schema,
        }
        # Validate the BagIt metadata with JSONSchema
        schema_path = current_jsonschemas.url_to_path(bagit_schema)
        schema = current_jsonschemas.get_schema(schema_path)
        validate(bagit_metadata, schema)

        # Create the BagIt schema object
        with db.session.begin_nested():
            obj = SIPMetadata(
                sip_id=self.sip.id,
                type_id=BagItArchiver._get_bagit_metadata_type().id,
                content=json.dumps(bagit_metadata))
            db.session.add(obj)

    def write_all_files(self):
        """Write all of the archived files to the archive file system."""
        bagit_meta = self.get_bagit_metadata(self.sip, as_dict=True)
        if not bagit_meta:
            all_files = self.get_all_files()
            self.save_bagit_metadata(all_files)
            bagit_meta = self.get_bagit_metadata(self.sip, as_dict=True)

        write_filesinfo = [fi for fi in bagit_meta['files']
                           if not self._is_fetched(fi)]
        return super(BagItArchiver, self).write_all_files(
            filesinfo=write_filesinfo)

    @staticmethod
    def _get_checksum(checksum, expected='md5'):
        """Return the checksum if the type is the expected."""
        checksum = checksum.split(':')
        if checksum[0] != expected or len(checksum) != 2:
            raise AttributeError('Checksum format is not correct.')
        else:
            return checksum[1]
