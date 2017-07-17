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

import json
from copy import deepcopy
from datetime import datetime

from flask import current_app
from fs.path import join
from invenio_db import db
from invenio_jsonschemas.errors import JSONSchemaNotFound

from jsonschema import validate

from invenio_sipstore.archivers import BaseArchiver
from invenio_sipstore.models import SIPMetadata, SIPMetadataType, \
    current_jsonschemas


class BagItArchiver(BaseArchiver):
    """BagIt archiver for SIP files."""

    # Name of the SIPMetadataType for internal use of BagItArchiver
    bagit_metadata_type_name = 'bagit'

    def __init__(self, sip, tags=None):
        """Constuctor.

        :param sip: API instance of the SIP that is to be archived.
        :type sip: invenio_sipstore.api.SIP
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

    @classmethod
    def get_bagit_metadata_type(cls):
        """Property for the metadata type for BagIt generation."""
        return SIPMetadataType.get_from_name(cls.bagit_metadata_type_name)

    @classmethod
    def get_bagit_metadata(cls, sip):
        """Fetch the BagIt metadata information.

        :param sip: SIP for which to fetch the metadata.

        :returns: Return the BagIt metadata information (SIPMetadata) instace
            or None if the object does not exist.
        """
        return SIPMetadata.query.filter_by(
            sip_id=sip.id,
            type_id=cls.get_bagit_metadata_type().id).one_or_none()

    @classmethod
    def get_bagit_metadata_json(cls, sip):
        """Get the JSON (dict) of the associated BagIt metadata.

        Shortcut method for loading the JSON directly from the associated
        SIPMetadata object.
        """
        bagit_meta = cls.get_bagit_metadata(sip)
        if bagit_meta:
            return json.loads(bagit_meta.content)
        else:
            return None

    def _is_fetched(self, file_info):
        """Determine if file info specifies a file that is fetched."""
        return 'fetched' in file_info and file_info['fetched']

    def create_bagit_metadata(
            self, patch_of=None, include_missing_files=False,
            filesdir='data/files', metadatadir='data/metadata'):
        """Create the BagIt metadata object."""
        sip_data_files = []  # Record's data + Record metadata dumps

        sipfiles = self.sip.files
        if patch_of:
            sipfiles = []  # We select SIPFiles for writing manually
            prev_files = self.get_bagit_metadata_json(patch_of)['datafiles']

            # Helper mappings
            # File UUID-to-manifest-item mapping (select only the data files,
            # not the metadata).
            id2mi = dict((f['file_uuid'], f) for f in
                         prev_files if 'file_uuid' in f)
            # File UUID-to-SIP File mapping
            id2sf = dict((str(file.file.id), file) for file in self.sip.files)

            manifest_files_s = set(id2mi.keys())
            sip_files_s = set(id2sf.keys())
            if include_missing_files:
                fetched_uuids = manifest_files_s
            else:
                fetched_uuids = manifest_files_s & sip_files_s
            stored_uuids = sip_files_s - manifest_files_s

            for uuid in fetched_uuids:
                fi = deepcopy(id2mi[uuid])
                if uuid in id2sf:
                    filename = join(filesdir, id2sf[uuid].filepath)
                else:
                    filename = id2mi[uuid]['filename']
                fi['filename'] = filename
                fi['fetched'] = True
                sip_data_files.append(fi)

            for uuid in stored_uuids:
                sipfiles.append(id2sf[uuid])

        # Copy the files
        files_info = super(BagItArchiver, self).create(
            filesdir=filesdir, metadatadir=metadatadir, sipfiles=sipfiles,
            dry_run=True)
        sip_data_files.extend(files_info)
        # Add the files from fetch.txt to the files_info dictionary,
        # so they will be included in generated manifest-md5.txt file

        self.autogenerate_tags(files_info)

        # Generate the BagIt metadata files (manifest-md5.txt, bagit.txt etc.)
        bagit_meta_files = []
        if any(self._is_fetched(fi) for fi in sip_data_files):
            funcs = [((self.get_fetch_file, (sip_data_files, ), )), ]
        else:
            funcs = []
        funcs.extend([
            (self.get_manifest_file, (sip_data_files, ), ),
            (self.get_bagit_file, (), ),
            (self.get_baginfo_file, (), ),
            (self.get_tagmanifest, (bagit_meta_files, ), ),  # Needs to be last
        ])

        for func, args in funcs:
            fn, content = func(*args)
            fi = self._save_file(fn, content, dry_run=True)
            fi['content'] = content
            bagit_meta_files.append(fi)

        bagit_schema = current_jsonschemas.path_to_url(
            current_app.config['SIPSTORE_DEFAULT_BAGIT_JSONSCHEMA'])
        bagit_metadata = {
            'datafiles': sip_data_files,
            'bagitfiles': bagit_meta_files,
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
                type_id=BagItArchiver.get_bagit_metadata_type().id,
                content=json.dumps(bagit_metadata))
            db.session.add(obj)

    def create(self, patch_of=None, include_missing_files=False,
               filesdir="data/files", metadatadir="data/metadata"):
        """Archive the SIP generating a BagIt file.

        When specifying 'patch_of' parameter the 'include_missing_files'
        flag determines whether files that are missing in the archived SIP
        (w.r.t. the SIP specified in 'patch_of') should be treated as
        explicitly deleted (include_missing_files=False) or if they
        should still be included in the manifest.

        Example:
            include_missing_files = True
              SIP_1:
                SIPFiles: a.txt, b.txt
                BagIt Manifest: a.txt, b.txt
              SIP_2 (Bagged with patch_of=SIP_1):
                SIPFiles: b.txt, c.txt
                BagIt Manifest: a.txt, b.txt, c.txt
                fetch.txt: a.txt, b.txt

            include_missing_files = False
              SIP_1:
                SIPFiles: a.txt, b.txt
                BagIt Manifest: a.txt, b.txt
              SIP_2 (Bagged with patch_of=SIP_1):
                SIPFIles: b.txt, c.txt
                BagIt Manifest: b.txt, c.txt
                fetch.txt: b.txt

        :param bool create_bagit_metadata: At the end of archiving,
            create a SIPMetadata object for this SIP, which
            will contain the metadata of the BagIt contents.
            It is necessary to bag the SIPs with this option enabled, if
            one wants to make use of 'patch_of' later on.
        :param patch_of: Write a lightweight BagIt, which will archive only
            the new files, and refer to the repeated ones in "fetch.txt" file.
            The provided argument is a SIP, which will be taken as a base
            for determining the "diff" between two bags.
            Provided SIP needs to have a special 'bagit'-named SIPMetadata
            object associated with it, i.e. it had to have been previously
            archived with the 'create_bagit_metadata' flag.
        :type patch_of: invenio_sipstore.models.SIP or None
        :type bool include_missing_files: If set to True and if 'patch_of' is
            used, include the files that are missing in the SIP w.r.t. to
            the 'patch_of' SIP in the manifest.
            The opposite (include_missing_files=False) is equivalent to
            treating those as explicitly deleted - the files will not be
            included in the manifest, nor in the "fetch.txt" file.
        :returns: a dictionary with the filenames as keys, and size and
            checksum as value
        :rtype: dict
        """
        bagit_meta = self.get_bagit_metadata_json(self.sip)
        if not bagit_meta:
            self.create_bagit_metadata(
                patch_of=patch_of, include_missing_files=include_missing_files,
                filesdir=filesdir, metadatadir=metadatadir)
            bagit_meta = self.get_bagit_metadata_json(self.sip)

        archived_data = [fi for fi in bagit_meta['datafiles']
                         if not self._is_fetched(fi) and 'file_uuid' in fi]
        fetched_data = [fi for fi in bagit_meta['datafiles']
                        if self._is_fetched(fi)]
        archived_s = set([f['file_uuid'] for f in archived_data])

        # Create a set for fetching
        sipfiles = [f for f in self.sip.files if str(f.file.id) in archived_s]
        files_info = super(BagItArchiver, self).create(
            filesdir=filesdir, metadatadir=metadatadir, sipfiles=sipfiles)

        files_info.extend(fetched_data)

        for fi in bagit_meta['bagitfiles']:
            out_fi = self._save_file(fi['filename'], fi['content'])
            assert fi['path'] == out_fi['path']
            files_info.append(out_fi)

        return files_info

    def autogenerate_tags(self, files_info):
        """Generate the automatic tags."""
        self.tags['Bagging-Date'] = datetime.now().strftime(
            "%Y-%m-%d_%H:%M:%S:%f")
        self.tags['Payload-Oxum'] = '{0}.{1}'.format(
            sum([f['size'] for f in files_info]), len(files_info))

    def get_fetch_file(self, files_info):
        """Generate the contents of the fetch.txt file."""
        content = ('{0} {1} {2}'.format(f['path'], f['size'], f['filename'])
                   for f in files_info if self._is_fetched(f))
        return 'fetch.txt', '\n'.join(content)

    def get_manifest_file(self, files_info):
        """Create the manifest file specifying the checksum of the files.

        :return: the name of the file and its content
        :rtype: tuple
        """
        content = ('{0} {1}'.format(self._get_checksum(
                   f['checksum']), f['filename']) for f in files_info)
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
        files_info = [fi for fi in files_info if fi['filename']]
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
