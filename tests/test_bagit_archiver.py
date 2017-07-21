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
from helpers import get_file
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
    files_info = [
        {
            'filename': 'file1',
            'size': 42,
        },
        {
            'filename': 'file2',
            'size': 42,
        },
        {
            'filename': 'file3',
            'size': 42,
        },
        {
            'filename': 'file4',
            'size': 42,
        },
        {
            'filename': 'file5',
            'size': 42,
        },
    ]
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
    files_info = [
        {
            'filename': 'file1',
            'checksum': 'md5:13',
        },
        {
            'filename': 'file2',
            'checksum': 'md5:37',
        }
    ]
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
    files_info = [
        {
            'filename': 'file1',
            'checksum': 'md5:13'
        },
        {
            'filename': None,
            'checksum': 'md5:37',
        }
    ]
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
    assert get_file('data/metadata/json-test.json', result)
    assert get_file('data/files/foobar.txt', result)
    assert get_file('manifest-md5.txt', result)
    assert get_file('bagit.txt', result)
    assert get_file('bag-info.txt', result)
    assert get_file('tagmanifest-md5.txt', result)
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
    archiver.create()

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

    return sip1, sip2, file1, file2, file3, archiver


def test_bagit_archiver_create_archive_fetch_file(
        archived_bagit_sip, dummy_location, db, sip_with_file,
        tmp_archive_fs):
    """Test the BagIt archiving with previous SIP as a base for diffing."""
    sip1, sip2, file1, file2, file3, archiver = archived_bagit_sip
    # create a BagIt for the SIP 2, but make it a patch of the SIP 1
    result = archiver.create(patch_of=sip1, include_missing_files=True)

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
    assert get_file('data/metadata/json-test.json', result)
    assert get_file('data/metadata/xml-test.xml', result)
    assert get_file('data/files/foobar.txt', result)
    # Check if the correct file was referenced
    assert get_file('data/files/foobar.txt', result)['file_uuid'] == \
        str(file1.id)
    assert get_file('data/files/foobar2-renamed.txt', result)
    assert get_file('data/files/foobar2-renamed.txt', result)['file_uuid'] == \
        str(file2.id)
    assert get_file('data/files/foobar3.txt', result)
    assert get_file('manifest-md5.txt', result)
    assert get_file('bagit.txt', result)
    assert get_file('bag-info.txt', result)
    assert get_file('tagmanifest-md5.txt', result)
    assert get_file('fetch.txt', result)

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

    sip1_bagit_meta = {
        '$schema': 'https://localhost/schemas/sipstore/bagit-v1.0.0.json',
        'manifest': [
            {
                'checksum': 'md5:098f6bcd4621d373cade4e832627b4f6',
                'file_uuid': file1.id,
                'filename': 'data/files/foobar.txt',
                'path': tmp_archive_fs.getsyspath(
                    'test/data/files/foobar.txt'),
                'size': 4,
            },
            {
                'checksum': 'md5:652b054df498ace88fef9857785fce34',
                'file_uuid': file2.id,
                'filename': 'data/files/foobar2.txt',
                'path': tmp_archive_fs.getsyspath(
                    'test/data/files/foobar2.txt'),
                'size': 11},
            {
                'checksum': 'md5:2e543b56c27ade33aad2d5eb870b23ba',
                'filename': 'data/metadata/json-test.json',
                'path': tmp_archive_fs.getsyspath(
                    'test/data/metadata/json-test.json'),
                'size': 22
            }
        ]
    }
    BagItArchiver.get_bagit_metadata(sip1) == sip1_bagit_meta

    sip2_bagit_meta = {
        "$schema": "https://localhost/schemas/sipstore/bagit-v1.0.0.json",
        "fetch": [
            {
                "size": 11,
                "checksum": "md5:652b054df498ace88fef9857785fce34",
                "filename": "data/files/foobar2-renamed.txt",
                "file_uuid": file2.id,
                'path': tmp_archive_fs.getsyspath(
                    'test/data/files/foobar2.txt'),
            },
            {
                "size": 11,
                "checksum": "md5:652b054df498ace88fef9857785fce34",
                "filename": "data/files/foobar2-renamed.txt",
                "file_uuid": file2.id,
                'path': tmp_archive_fs.getsyspath(
                    'test/data/files/foobar2.txt'),
            }
        ],
        "manifest": [
            {
                "checksum": "md5:f1d2f9e84f147fed5fab05c6f8210c6f",
                'path': tmp_archive_fs.getsyspath(
                    'test/data/files/foobar3.txt'),
                "filename": "data/files/foobar3.txt",
                "file_uuid": file3.id,
                "size": 10
            },
            {
                "checksum": "md5:3acfb5b50e960eece15dbed928d9e40f",
                'path': tmp_archive_fs.getsyspath(
                    'test/data/metadata/xml-test.xml'),
                "filename": "data/metadata/xml-test.xml",
                "size": 17
            },
            {
                "checksum": "md5:1963a365b400a214cf9b89354bcd6169",
                'path': tmp_archive_fs.getsyspath(
                    'test/data/metadata/json-test.json'),
                "filename": "data/metadata/json-test.json",
                "size": 24
            },
            {
                "size": 11,
                "checksum": "md5:652b054df498ace88fef9857785fce34",
                "filename": "data/files/foobar2-renamed.txt",
                "file_uuid": file2.id,
                'path': tmp_archive_fs.getsyspath(
                    'test/data/files/foobar2.txt'),
            }
        ]
    }
    BagItArchiver.get_bagit_metadata(sip2) == sip2_bagit_meta


def test_bagit_archiver_create_archive_fetch_file_deleted(
        archived_bagit_sip, dummy_location, db, sip_with_file,
        tmp_archive_fs):
    """
    Test the BagIt archiving with previous SIP as a base for diffing.

    Treats missing files as deleted.
    """
    sip1, sip2, file1, file2, file3, archiver = archived_bagit_sip
    # create a BagIt for the SIP 2, but make it a patch of the SIP 1
    result = archiver.create(patch_of=sip1, include_missing_files=False)

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
    assert get_file('data/metadata/json-test.json', result)
    assert get_file('data/metadata/xml-test.xml', result)
    # The file ommited from SIP should not be specified
    assert not get_file('data/files/foobar.txt', result)
    # Check if the correct file was referenced
    assert get_file('data/files/foobar2-renamed.txt', result)
    assert get_file('data/files/foobar2-renamed.txt', result)['file_uuid'] == \
        str(file2.id)
    assert get_file('data/files/foobar3.txt', result)
    assert get_file('manifest-md5.txt', result)
    assert get_file('bagit.txt', result)
    assert get_file('bag-info.txt', result)
    assert get_file('tagmanifest-md5.txt', result)
    assert get_file('fetch.txt', result)

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

    sip2_bagit_meta = {
        "$schema": "https://localhost/schemas/sipstore/bagit-v1.0.0.json",
        "fetch": [
            {
                "size": 11,
                "checksum": "md5:652b054df498ace88fef9857785fce34",
                "filename": "data/files/foobar2-renamed.txt",
                "file_uuid": "2b5ae0dd-9ef1-4194-a675-a0daef49b001",
                'path': tmp_archive_fs.getsyspath(
                    'test/data/files/foobar2.txt'),
            }
        ],
        "manifest": [
            {
                "checksum": "md5:f1d2f9e84f147fed5fab05c6f8210c6f",
                'path': tmp_archive_fs.getsyspath(
                    'test/data/files/foobar3.txt'),
                "filename": "data/files/foobar3.txt",
                "file_uuid": file3.id,
                "size": 10
            },
            {
                "checksum": "md5:3acfb5b50e960eece15dbed928d9e40f",
                'path': tmp_archive_fs.getsyspath(
                    'test/data/metadata/xml-test.xml'),
                "filename": "data/metadata/xml-test.xml",
                "size": 17
            },
            {
                "checksum": "md5:1963a365b400a214cf9b89354bcd6169",
                'path': tmp_archive_fs.getsyspath(
                    'test/data/metadata/json-test.json'),
                "filename": "data/metadata/json-test.json",
                "size": 24
            },
            {
                "size": 11,
                "checksum": "md5:652b054df498ace88fef9857785fce34",
                "filename": "data/files/foobar2-renamed.txt",
                "file_uuid": file2.id,
                'path': tmp_archive_fs.getsyspath(
                    'test/data/files/foobar2.txt'),
            }
        ]
    }
    BagItArchiver.get_bagit_metadata(sip2) == sip2_bagit_meta
