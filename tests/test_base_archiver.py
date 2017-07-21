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

"""Module tests for the BaseArchiver class."""

from __future__ import absolute_import, print_function

from hashlib import md5

from helpers import get_file

from invenio_sipstore.api import SIP
from invenio_sipstore.archivers import BaseArchiver
from invenio_sipstore.models import SIPMetadataType


def calculate_md5(fs, filename):
    """Calculate the MD5 of the content of a file."""
    with fs.open(filename) as fp:
        return md5(fp.read().encode('utf-8')).hexdigest()


def test_base_archiver_getters(db, sip_with_file):
    """Test the constructor and the getters."""
    sip = SIP(sip_with_file)
    # constructor
    archiver = BaseArchiver(sip)
    assert archiver.sip is sip
    # get files
    file = sip.files[0]
    files = archiver.get_files()
    assert len(files) == 1
    assert file.filepath in files
    assert files[file.filepath] == file.storage_location
    # get metadata
    mjson = SIPMetadataType(title='JSON Test', name='json-test',
                            format='json', schema='url')
    marcxml = SIPMetadataType(title='MARC XML Test', name='marcxml-test',
                              format='xml', schema='uri')
    db.session.add(mjson)
    db.session.add(marcxml)
    sip.attach_metadata('marcxml-test', '<this>is xml</this>')
    sip.attach_metadata('json-test', '{"title": "json"}')
    db.session.commit()
    metadata = archiver.get_metadata()
    assert len(metadata) == 2
    assert 'json-test.json' in metadata
    assert 'marcxml-test.xml' in metadata
    assert metadata['json-test.json'] == '{"title": "json"}'
    # all files
    assert len(archiver.get_all_files()) == len(metadata) + len(files)


def test_base_archiver_create_directories(tmp_archive_fs):
    """Test the _create_directories function."""
    archiver = BaseArchiver(None)
    archiver.fs = tmp_archive_fs
    archiver._create_directories('lol/test')
    assert tmp_archive_fs.exists('lol/test/')


def test_base_archiver_save_file(tmp_archive_fs):
    """Test the _save_file function."""
    archiver = BaseArchiver(None)
    archiver.fs = tmp_archive_fs
    content = 'this is a content'
    result = archiver._save_file('test/file.txt', content)
    assert tmp_archive_fs.isfile('test/file.txt')
    assert result['filename'] == 'test/file.txt'
    assert result['size'] == len(content)
    assert 'md5:' + calculate_md5(tmp_archive_fs, 'test/file.txt') \
        == result['checksum']


def test_base_archiver_copy_files(sip_with_file, tmp_archive_fs):
    """Test the _copy_files function."""
    sip = SIP(sip_with_file)
    archiver = BaseArchiver(sip)
    archiver.fs = tmp_archive_fs
    result = archiver._copy_files(sip.files, 'test')
    assert tmp_archive_fs.isfile('test/foobar.txt')
    assert len(result) == 1
    assert any('test/foobar.txt' == f['filename'] for f in result)
    # assert result['test/foobar.txt']['size'] == len('test')
    assert 'md5:' + calculate_md5(tmp_archive_fs, 'test/foobar.txt') \
        == get_file('test/foobar.txt', result)['checksum']


def test_base_archiver_create_archive(db, sip_with_file, tmp_archive_fs):
    """Test the functions used to create an export of the SIP."""
    sip = SIP(sip_with_file)
    mtype = SIPMetadataType(title='JSON Test', name='json-test',
                            format='json', schema='url://to/schema')
    db.session.add(mtype)
    sip.attach_metadata('json-test', '{"title": "json"}')
    db.session.commit()
    archiver = BaseArchiver(sip)
    # init
    archiver.init(tmp_archive_fs, 'test')
    path = archiver.path
    assert tmp_archive_fs.isdir(path)
    # create
    result = archiver.create(filesdir="files", metadatadir="meta")
    assert tmp_archive_fs.isfile('test/meta/json-test.json')
    assert tmp_archive_fs.isfile('test/files/foobar.txt')
    assert len(result) == 2
    assert get_file('meta/json-test.json', result)
    assert get_file('files/foobar.txt', result)
    # finalize
    archiver.finalize()
    assert archiver.path == ''
    assert not tmp_archive_fs.exists(path)
