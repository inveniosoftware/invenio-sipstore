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
from invenio_files_rest.models import FileInstance
from six import BytesIO

from invenio_sipstore.api import SIP
from invenio_sipstore.archivers import BagItArchiver
from invenio_sipstore.models import SIP as SIPModel
from invenio_sipstore.models import SIPFile


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


def test_bagit_archiver_create_archive(db, sip_with_file, tmp_archive_fs,
                                       sip_metadata_types):
    """Test the functions used to create an export of the SIP."""
    sip = SIP(sip_with_file)
    sip.attach_metadata('json-test', '{"title": "json"}')
    db.session.commit()
    archiver = BagItArchiver(sip)
    # init
    archiver.init(tmp_archive_fs, 'test')
    path = archiver.path
    assert tmp_archive_fs.isdir(path)
    # create
    result = archiver.create()
    assert tmp_archive_fs.isfile('test/data/metadata/json-test.json')
    assert tmp_archive_fs.isfile('test/data/files/foobar.txt')
    assert tmp_archive_fs.isfile('test/manifest-md5.txt')
    assert tmp_archive_fs.isfile('test/bagit.txt')
    assert tmp_archive_fs.isfile('test/bag-info.txt')
    assert tmp_archive_fs.isfile('test/tagmanifest-md5.txt')
    assert len(result) == 6
    assert 'data/metadata/json-test.json' in result
    assert 'data/files/foobar.txt' in result
    assert 'manifest-md5.txt' in result
    assert 'bagit.txt' in result
    assert 'bag-info.txt' in result
    assert 'tagmanifest-md5.txt' in result
    # finalize
    archiver.finalize()
    assert archiver.path == ''
    assert not tmp_archive_fs.exists(path)


@pytest.fixture
def archived_bagit_sip(db, dummy_location, sip_with_file, tmp_archive_fs,
                       sip_metadata_types):
    """Fixture with two sips and multiple files for BagIt archiver tests."""
    # For better example, add an extra file to the SIP
    sip1 = SIP(sip_with_file)
    file1 = sip1.files[0].file
    file2 = FileInstance.create()
    file2.set_contents(BytesIO(b'test-second'),
                       default_location=dummy_location.uri)
    sipfile2 = SIPFile(sip_id=sip1.id, filepath="foobar2.txt",
                       file_id=file2.id)
    db.session.add(sipfile2)
    sip1.attach_metadata('json-test', '{"title": "JSON Meta"}')
    db.session.commit()

    archiver = BagItArchiver(sip1)
    # init
    archiver.init(tmp_archive_fs, 'test')
    # create
    archiver.create(create_bagit_metadata=True)

    # Make a new SIP with one of the previous file and a new one
    sip2 = SIP(SIPModel.create())
    sip2.attach_metadata('json-test', '{"title": "JSON Meta 2"}')
    sip2.attach_metadata('xml-test', '<p>XML Meta 2</p>')
    file3 = FileInstance.create()
    file3.set_contents(BytesIO(b'test-third'),
                       default_location=dummy_location.uri)
    # We name rename the filepath of the second SIP file on purpose
    # ('foobar2.txt' -> 'foobar22.txt')
    sip2file2 = SIPFile(sip_id=sip2.id, filepath="foobar2-renamed.txt",
                        file_id=file2.id)
    sip2file3 = SIPFile(sip_id=sip2.id, filepath="foobar3.txt",
                        file_id=file3.id)

    db.session.add(sip2file2)
    db.session.add(sip2file3)
    db.session.commit()

    archiver = BagItArchiver(sip2)
    archiver.init(tmp_archive_fs, 'test2')

    return sip1, file1, file2, file3, archiver


def test_bagit_archiver_create_archive_fetch_file(
        archived_bagit_sip, dummy_location, db, sip_with_file,
        tmp_archive_fs):
    """Test the BagIt archiving with previous SIP as a base for diffing."""

    sip1, file1, file2, file3, archiver = archived_bagit_sip
    # create a BagIt for the SIP 2, but make it a patch of the SIP 1
    result = archiver.create(create_bagit_metadata=True, patch_of=sip1,
                             include_missing_files=True)

    assert tmp_archive_fs.isfile('test2/data/metadata/json-test.json')
    assert tmp_archive_fs.isfile('test2/data/metadata/xml-test.xml')

    # The two referenced files should not exist in the archive
    assert not tmp_archive_fs.isfile('test2/data/files/foobar.txt')
    assert not tmp_archive_fs.isfile('test2/data/files/foobar2-renamed.txt')
    # Ony the new one should
    assert tmp_archive_fs.isfile('test2/data/files/foobar3.txt')

    assert tmp_archive_fs.isfile('test2/manifest-md5.txt')
    assert tmp_archive_fs.isfile('test2/fetch.txt')
    assert tmp_archive_fs.isfile('test2/bagit.txt')
    assert tmp_archive_fs.isfile('test2/bag-info.txt')
    assert tmp_archive_fs.isfile('test2/tagmanifest-md5.txt')

    assert len(result) == 10
    assert 'data/metadata/json-test.json' in result
    assert 'data/metadata/xml-test.xml' in result
    assert 'data/files/foobar.txt' in result
    # Check if the correct file was referenced
    assert result['data/files/foobar.txt']['file_uuid'] == str(file1.id)
    assert 'data/files/foobar2-renamed.txt' in result
    assert result['data/files/foobar2-renamed.txt']['file_uuid'] == \
        str(file2.id)
    assert 'data/files/foobar3.txt' in result
    assert 'manifest-md5.txt' in result
    assert 'bagit.txt' in result
    assert 'bag-info.txt' in result
    assert 'tagmanifest-md5.txt' in result
    assert 'fetch.txt' in result

    # Should be specified in the fetch and manifest
    with tmp_archive_fs.open('test2/fetch.txt') as fp:
        expected_fetch = [
            "{0} 4 data/files/foobar.txt".format(
                tmp_archive_fs.getsyspath('test/data/files/foobar.txt')),
            "{0} 11 data/files/foobar2-renamed.txt".format(
                tmp_archive_fs.getsyspath('test/data/files/foobar2.txt')),
            ]
        fetch = fp.read().splitlines()
        assert all(item in fetch for item in expected_fetch)

    with tmp_archive_fs.open('test2/manifest-md5.txt') as fp:
        expected_manifest = [
            u'1963a365b400a214cf9b89354bcd6169 data/metadata/json-test.json',
            u'3acfb5b50e960eece15dbed928d9e40f data/metadata/xml-test.xml',
            u'098f6bcd4621d373cade4e832627b4f6 data/files/foobar.txt',
            u'652b054df498ace88fef9857785fce34 data/files/foobar2-renamed.txt',
            u'f1d2f9e84f147fed5fab05c6f8210c6f data/files/foobar3.txt',
        ]

        manifest = fp.read().splitlines()
        assert all(item in manifest for item in expected_manifest)


def test_bagit_archiver_create_archive_fetch_file_deleted(
        archived_bagit_sip, dummy_location, db, sip_with_file,
        tmp_archive_fs):
    """
    Test the BagIt archiving with previous SIP as a base for diffing.

    Treats missing files as deleted.
    """

    sip1, file1, file2, file3, archiver = archived_bagit_sip
    # create a BagIt for the SIP 2, but make it a patch of the SIP 1
    result = archiver.create(create_bagit_metadata=True, patch_of=sip1,
                             include_missing_files=False)

    assert tmp_archive_fs.isfile('test2/data/metadata/json-test.json')
    assert tmp_archive_fs.isfile('test2/data/metadata/xml-test.xml')

    # The "deleted" (missing in SIP) file should not be archived
    assert not tmp_archive_fs.isfile('test2/data/files/foobar.txt')
    # The referenced file should not exist in the archive
    assert not tmp_archive_fs.isfile('test2/data/files/foobar2-renamed.txt')
    # Ony the new one should exist
    assert tmp_archive_fs.isfile('test2/data/files/foobar3.txt')

    assert tmp_archive_fs.isfile('test2/manifest-md5.txt')
    assert tmp_archive_fs.isfile('test2/fetch.txt')
    assert tmp_archive_fs.isfile('test2/bagit.txt')
    assert tmp_archive_fs.isfile('test2/bag-info.txt')
    assert tmp_archive_fs.isfile('test2/tagmanifest-md5.txt')

    assert len(result) == 9
    assert 'data/metadata/json-test.json' in result
    assert 'data/metadata/xml-test.xml' in result
    # The file ommited from SIP should not be specified
    assert 'data/files/foobar.txt' not in result
    # Check if the correct file was referenced
    assert 'data/files/foobar2-renamed.txt' in result
    assert result['data/files/foobar2-renamed.txt']['file_uuid'] == \
        str(file2.id)
    assert 'data/files/foobar3.txt' in result
    assert 'manifest-md5.txt' in result
    assert 'bagit.txt' in result
    assert 'bag-info.txt' in result
    assert 'tagmanifest-md5.txt' in result
    assert 'fetch.txt' in result

    # File should be specified in the fetch and manifest
    with tmp_archive_fs.open('test2/fetch.txt') as fp:
        expected_fetch = [
            "{0} 11 data/files/foobar2-renamed.txt".format(
                tmp_archive_fs.getsyspath('test/data/files/foobar2.txt')),
            ]
        fetch = fp.read().splitlines()
        assert set(fetch) == set(expected_fetch)
        assert all(item in fetch for item in expected_fetch)

    with tmp_archive_fs.open('test2/manifest-md5.txt') as fp:
        expected_manifest = [
            u'1963a365b400a214cf9b89354bcd6169 data/metadata/json-test.json',
            u'3acfb5b50e960eece15dbed928d9e40f data/metadata/xml-test.xml',
            u'652b054df498ace88fef9857785fce34 data/files/foobar2-renamed.txt',
            u'f1d2f9e84f147fed5fab05c6f8210c6f data/files/foobar3.txt',
        ]

        manifest = fp.read().splitlines()
        assert set(manifest) == set(expected_manifest)
