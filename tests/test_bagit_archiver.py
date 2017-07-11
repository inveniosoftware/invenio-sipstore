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

"""Module tests for the BagItArchiver class."""

from __future__ import absolute_import, print_function

import pytest

from invenio_sipstore.api import SIP
from invenio_sipstore.archivers import BagItArchiver
from invenio_sipstore.models import SIPMetadataType


def test_bagit_archiver_get_all_files(sip_with_file):
    """Test the function get_all_files."""
    sip = SIP(sip_with_file)
    archiver = BagItArchiver(sip)
    fileset = {'manifest-md5.txt', 'bagit.txt', 'bag-info.txt',
               'tagmanifest-md5.txt'}
    files = archiver.get_all_files()
    assert len(files) == len(archiver.get_files()) \
        + len(archiver.get_metadata()) \
        + len(fileset)
    assert fileset < set(files)


def test_bagit_archiver_get_checksum():
    """Test the function _get_checksum."""
    with pytest.raises(AttributeError):
        BagItArchiver._get_checksum('sha1:12')
    with pytest.raises(AttributeError):
        BagItArchiver._get_checksum('md5')
    assert BagItArchiver._get_checksum('md5:12') == '12'


def test_bagit_archiver_autogenerate_tags():
    """Test the function autogenerate_tags."""
    archiver = BagItArchiver(None, tags={'test': 'concluant'})
    files_info = {
        'file1': {'size': 42},
        'file2': {'size': 42},
        'file3': {'size': 42},
        'file4': {'size': 42},
        'file5': {'size': 42}
    }
    archiver.autogenerate_tags(files_info)
    tags = archiver.tags
    assert 'test' in tags
    assert tags['test'] == 'concluant'
    assert 'Bagging-Date' in tags
    assert 'Payload-Oxum' in tags
    assert tags['Payload-Oxum'] == '{0}.{1}'.format(5 * 42, 5)


def test_bagit_archiver_get_manifest_file():
    """Test the function get_manifest_file."""
    archiver = BagItArchiver(None)
    files_info = {
        'file1': {'checksum': 'md5:13'},
        'file2': {'checksum': 'md5:37'}
    }
    name, content = archiver.get_manifest_file(files_info)
    assert name == 'manifest-md5.txt'
    assert '13 file1' in content
    assert '37 file2' in content


def test_bagit_archiver_get_bagit_file():
    """Test the function get_bagit_file."""
    archiver = BagItArchiver(None)
    name, cont = archiver.get_bagit_file()
    assert name == 'bagit.txt'
    assert cont == 'BagIt-Version: 0.97\nTag-File-Character-Encoding: UTF-8'


def test_bagit_archiver_get_baginfo_file():
    """Test the function get_baginfo_file."""
    tags = {
        'tag1': 'value1',
        'no': 'inspiration'
    }
    archiver = BagItArchiver(None, tags=tags)
    name, content = archiver.get_baginfo_file()
    assert name == 'bag-info.txt'
    assert 'tag1: value1' in content
    assert 'no: inspiration' in content


def test_bagit_archiver_get_tagmanifest():
    """Test the function get_tagmanifest."""
    archiver = BagItArchiver(None)
    files_info = {
        'file1': {'checksum': 'md5:13'},
        None: {'checksum': 'md5:37'}
    }
    name, content = archiver.get_tagmanifest(files_info)
    assert name == 'tagmanifest-md5.txt'
    assert content == '13 file1'


def test_bagit_archiver_create_archive(db, sip_with_file, tmp_archive_fs):
    """Test the functions used to create an export of the SIP."""
    sip = SIP(sip_with_file)
    mtype = SIPMetadataType(title='JSON Test', name='json-test',
                            format='json', schema='url://to/schema')
    db.session.add(mtype)
    sip.attach_metadata('JSON Test', '{"title": "json"}')
    db.session.commit()
    archiver = BagItArchiver(sip)
    # init
    archiver.init(tmp_archive_fs, 'test')
    path = archiver.path
    assert tmp_archive_fs.isdir(path)
    # create
    result = archiver.create()
    assert tmp_archive_fs.isfile('test/data/json-test.json')
    assert tmp_archive_fs.isfile('test/data/files/foobar.txt')
    assert tmp_archive_fs.isfile('test/manifest-md5.txt')
    assert tmp_archive_fs.isfile('test/bagit.txt')
    assert tmp_archive_fs.isfile('test/bag-info.txt')
    assert tmp_archive_fs.isfile('test/tagmanifest-md5.txt')
    assert len(result) == 6
    assert 'data/json-test.json' in result
    assert 'data/files/foobar.txt' in result
    assert 'manifest-md5.txt' in result
    assert 'bagit.txt' in result
    assert 'bag-info.txt' in result
    assert 'tagmanifest-md5.txt' in result
    # finalize
    archiver.finalize()
    assert archiver.path == ''
    assert not tmp_archive_fs.exists(path)
