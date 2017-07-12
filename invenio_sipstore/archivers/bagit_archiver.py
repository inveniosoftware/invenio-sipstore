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

from fs.path import join
from invenio_db import db

from invenio_sipstore.archivers import BaseArchiver
from invenio_sipstore.models import SIPMetadata, SIPMetadataType


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

    @property
    def bagit_metadata_type(self):
        """Property for the metadata type for BagIt generation."""
        return SIPMetadataType.get_from_name(self.bagit_metadata_type_name)

    def bagit_metadata(self, sip):
        """Property for fetching the BagIt metadata object."""
        bagit_meta = SIPMetadata.query.filter_by(
            sip_id=sip.id, type_id=self.bagit_metadata_type.id).one()
        return json.loads(bagit_meta.content)

    def create_bagit_metadata(self, content):
        """Create the BagIt metadata object."""
        with db.session.begin_nested():
            obj = SIPMetadata(sip_id=self.sip.id,
                              type_id=self.bagit_metadata_type.id,
                              content=content)
            db.session.add(obj)

    def create(self, create_bagit_metadata=False, patch_of=None,
               include_missing_files=False, filesdir="data/files",
               metadatadir="data/metadata"):
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
        sipfiles = self.sip.files
        if patch_of:
            fetch_info = {}
            sipfiles = []  # We select SIPFiles for writing manually
            sip_manifest = self.bagit_metadata(patch_of)['manifest']

            # Helper mappings
            # File UUID to manifest item mapping (select only the files data,
            # not metadata files).
            id2mi = dict((v['file_uuid'], dict(filename=k, meta=v)) for k, v in
                         sip_manifest.items() if 'file_uuid' in v)
            # File UUID to SIP File mapping
            id2sf = dict((str(file.file.id), file) for file in self.sip.files)

            manifest_files_s = set(id2mi.keys())
            sip_files_s = set(id2sf.keys())
            if include_missing_files:
                fetched_uuids = manifest_files_s
            else:
                fetched_uuids = manifest_files_s & sip_files_s
            stored_uuids = sip_files_s - manifest_files_s

            for uuid in fetched_uuids:
                if uuid in id2sf:
                    filename = join(filesdir, id2sf[uuid].filepath)
                else:
                    filename = id2mi[uuid]['filename']
                fetch_info[filename] = id2mi[uuid]['meta']

            for uuid in stored_uuids:
                sipfiles.append(id2sf[uuid])

        # Copy the files
        files_info = super(BagItArchiver, self).create(
            filesdir=filesdir, metadatadir=metadatadir, sipfiles=sipfiles)
        # Add the files from fetch.txt to the files_info dictionary,
        # so they will be included in generated manifest-md5.txt file
        if patch_of:
            files_info.update(fetch_info)

        self.autogenerate_tags(files_info)
        metadata_info = self._save_file(*self.get_manifest_file(files_info))
        if patch_of and fetch_info:
            # Write the fetch.txt file if any of the files are to be fetched
            metadata_info.update(
                self._save_file(*self.get_fetch_file(fetch_info)))
        metadata_info.update(self._save_file(*self.get_bagit_file()))
        metadata_info.update(self._save_file(*self.get_baginfo_file()))
        metadata_info.update(
            self._save_file(*self.get_tagmanifest(metadata_info)))

        if create_bagit_metadata:
            # Create a SIPMetadata file, which will store metadata on what we
            # have just archived using BagIt
            bagit_meta = {}
            bagit_meta['manifest'] = deepcopy(files_info)
            if patch_of and fetch_info:
                bagit_meta['fetch'] = deepcopy(fetch_info)
            self.create_bagit_metadata(json.dumps(bagit_meta))

        files_info.update(metadata_info)

        return files_info

    def autogenerate_tags(self, files_info):
        """Generate the automatic tags."""
        self.tags['Bagging-Date'] = datetime.now().strftime(
            "%Y-%m-%d_%H:%M:%S:%f")
        self.tags['Payload-Oxum'] = '{0}.{1}'.format(
            sum([f['size'] for f in files_info.values()]), len(files_info))

    def get_fetch_file(self, files_info):
        """Generate the contents of the fetch.txt file."""
        content = ('{0} {1} {2}'.format(c['path'], c['size'], f)
                   for f, c in files_info.items())
        return 'fetch.txt', '\n'.join(content)

    def get_manifest_file(self, files_info):
        """Create the manifest file specifying the checksum of the files.

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
