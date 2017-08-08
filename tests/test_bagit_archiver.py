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

from datetime import datetime
from hashlib import md5

import pytest

from invenio_sipstore.archivers import BagItArchiver


def fetch_file_endswith(sip, filename_suffix):
    """A helper method for fetching SIPFiles by the name suffix."""
    return next(f for f in sip.files if f.filepath.endswith(filename_suffix))


def test_get_checksum():
    """Test the function _get_checksum."""
    with pytest.raises(AttributeError):
        BagItArchiver._get_checksum('sha1:12')
    with pytest.raises(AttributeError):
        BagItArchiver._get_checksum('md5')
    assert BagItArchiver._get_checksum('md5:12') == '12'


def test_get_all_files(sips):
    """Test the function get_all_files."""
    archiver = BagItArchiver(sips[0])
    files = archiver.get_all_files()
    assert len(files) == 8


def test_write_all_files(sips, archive_fs):
    """Test the functions used to create an export of the SIP."""
    sip = sips[0]
    archiver = BagItArchiver(sip)
    assert not len(archive_fs.listdir())
    archiver.write_all_files()
    assert len(archive_fs.listdir()) == 1
    fs = archive_fs.opendir(archiver._get_archive_subpath())
    assert set(fs.listdir()) == \
        set(['tagmanifest-md5.txt', 'bagit.txt', 'manifest-md5.txt',
             'bag-info.txt', 'data', ])
    assert set(fs.listdir('data')) == \
        set(['metadata', 'files', 'filenames.txt'])
    assert set(fs.listdir('data/metadata')) == \
        set(['marcxml-test.xml', 'json-test.json', ])
    assert set(fs.listdir('data/files')) == set(['foobar.txt', ])


def _read_file(fs, filepath):
    with fs.open(filepath, 'r') as fp:
        content = fp.read()
    return {
        'checksum': md5(content.encode('utf-8')).hexdigest(),
        'size': len(content),
        'filepath': filepath,
    }


def test_write_patched(mocker, sips, archive_fs,
                       secure_sipfile_name_formatter):
    """Test the BagIt archiving with previous SIP as a base."""
    # Mock the bagging date generation so the 'Bagging-Date' tag is predefined
    dt = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S.%f")
    mocker.patch('invenio_sipstore.archivers.bagit_archiver.BagItArchiver.'
                 '_generate_bagging_date', return_value=dt)

    arch1 = BagItArchiver(sips[0])
    arch1.write_all_files()
    arch2 = BagItArchiver(sips[1], patch_of=sips[0])
    arch2.write_all_files()
    arch3 = BagItArchiver(sips[2], patch_of=sips[1],
                          include_all_previous=True)
    arch3.write_all_files()
    fs1 = archive_fs.opendir(arch1._get_archive_subpath())
    fs2 = archive_fs.opendir(arch2._get_archive_subpath())
    fs3 = archive_fs.opendir(arch3._get_archive_subpath())
    assert len(fs1.listdir()) == 5
    assert len(fs2.listdir()) == 6  # Includes 'fetch.txt'
    assert len(fs3.listdir()) == 6  # Includes 'fetch.txt'

    # Check SIP-1 archived contents
    assert set(fs1.listdir('data')) == \
        set(['files', 'metadata', 'filenames.txt'])
    assert len(fs1.listdir('data/files')) == 1
    assert len(fs1.listdir('data/metadata')) == 2
    assert len(fs2.listdir('data/files')) == 1
    assert len(fs2.listdir('data/metadata')) == 2
    assert len(fs3.listdir('data/files')) == 1
    assert len(fs3.listdir('data/metadata')) == 2

    # Fetch the filenames for easier fixture formatting below
    file1_fn = '{0}-foobar.txt'.format(
        fetch_file_endswith(sips[0], 'foobar.txt').file_id)
    file2_fn = '{0}-foobar2.txt'.format(
        fetch_file_endswith(sips[1], 'foobar2.txt').file_id)
    file3_fn = '{0}-foobar3.txt'.format(
        fetch_file_endswith(sips[2], 'foobar3.txt').file_id)
    file2_rn_fn = '{0}-foobar2-renamed.txt'.format(
        fetch_file_endswith(sips[2], 'foobar2-renamed.txt').file_id)
    # Both file2_fn and file2_rn_fn are referring to the same FileInstance,
    # so their UUID prefix should match
    assert file2_fn[:36] == file2_rn_fn[:36]
    expected_sip1 = [
        ('data/files/{0}'.format(file1_fn), 'test'),
        ('data/metadata/marcxml-test.xml', '<p>XML 1</p>'),
        ('data/metadata/json-test.json', '{"title": "JSON 1"}'),
        ('bagit.txt',
            'BagIt-Version: 0.97\nTag-File-Character-Encoding: UTF-8'),
        ('manifest-md5.txt', set([
            "{checksum} {filepath}".format(
                **_read_file(fs1, 'data/files/{0}'.format(file1_fn))),
            "{checksum} {filepath}".format(
                **_read_file(fs1, 'data/metadata/marcxml-test.xml')),
            "{checksum} {filepath}".format(
                **_read_file(fs1, 'data/metadata/json-test.json')),
            "{checksum} {filepath}".format(
                **_read_file(fs1, 'data/filenames.txt')),
        ])),
        ('data/filenames.txt', set([
            '{0} foobar.txt'.format(file1_fn),
        ])),
        ('bag-info.txt', (
            "Source-Organization: European Organization for Nuclear Research\n"
            "Organization-Address: CERN, CH-1211 Geneva 23, Switzerland\n"
            "Bagging-Date: {0}\n".format(dt) +
            "Payload-Oxum: 93.4\n"
            "External-Identifier: {0}/SIPBagIt-v1.0.0\n".format(sips[0].id) +
            "External-Description: BagIt archive of SIP."
        )),
    ]
    expected_sip2 = [
        ('data/files/{0}'.format(file2_fn), 'test-second'),
        ('data/metadata/marcxml-test.xml', '<p>XML 2</p>'),
        ('data/metadata/json-test.json', '{"title": "JSON 2"}'),
        ('bagit.txt',
            'BagIt-Version: 0.97\nTag-File-Character-Encoding: UTF-8'),
        ('fetch.txt', set(["{0} {1} {2}".format(
            fs1.getsyspath('data/files/{0}'.format(file1_fn)),
            4, 'data/files/{0}'.format(file1_fn)),
        ])),
        ('manifest-md5.txt', set([
            "{checksum} {filepath}".format(
                **_read_file(fs1, 'data/files/{0}'.format(file1_fn))),
            "{checksum} {filepath}".format(
                **_read_file(fs2, 'data/files/{0}'.format(file2_fn))),
            "{checksum} {filepath}".format(
                **_read_file(fs2, 'data/metadata/marcxml-test.xml')),
            "{checksum} {filepath}".format(
                **_read_file(fs2, 'data/metadata/json-test.json')),
            "{checksum} {filepath}".format(
                **_read_file(fs2, 'data/filenames.txt')),
        ])),
        ('data/filenames.txt', set([
            '{0} foobar.txt'.format(file1_fn),
            '{0} foobar2.txt'.format(file2_fn),
        ])),
        ('bag-info.txt', (
            "Source-Organization: European Organization for Nuclear Research\n"
            "Organization-Address: CERN, CH-1211 Geneva 23, Switzerland\n"
            "Bagging-Date: {0}\n".format(dt) +
            "Payload-Oxum: 165.5\n"
            "External-Identifier: {0}/SIPBagIt-v1.0.0\n".format(sips[1].id) +
            "External-Description: BagIt archive of SIP."
        )),
    ]
    expected_sip3 = [
        ('data/files/{0}'.format(file3_fn), 'test-third'),
        ('data/metadata/marcxml-test.xml', '<p>XML 3</p>'),
        ('data/metadata/json-test.json', '{"title": "JSON 3"}'),
        ('bagit.txt',
            'BagIt-Version: 0.97\nTag-File-Character-Encoding: UTF-8'),
        ('fetch.txt', set([
            "{0} {1} {2}".format(
                fs1.getsyspath('data/files/{0}'.format(file1_fn)),
                4, 'data/files/{0}'.format(file1_fn)),
            # Explanation on entry below: The file is fetched using original
            # filename (file2_fn) as it will be archived in SIP-2, however
            # the new destination has the 'renamed' filename (file2_rn_fn).
            # This is correct and expected behaviour
            "{0} {1} {2}".format(
                fs2.getsyspath('data/files/{0}'.format(file2_fn)),
                11, 'data/files/{0}'.format(file2_rn_fn)),
        ])),
        ('manifest-md5.txt', set([
            "{checksum} {filepath}".format(
                **_read_file(fs1, 'data/files/{0}'.format(file1_fn))),
            "{checksum} data/files/{newfilename}".format(
                newfilename=file2_rn_fn,
                **_read_file(fs2, 'data/files/{0}'.format(file2_fn))),
            "{checksum} {filepath}".format(
                **_read_file(fs3, 'data/files/{0}'.format(file3_fn))),
            "{checksum} {filepath}".format(
                **_read_file(fs3, 'data/metadata/marcxml-test.xml')),
            "{checksum} {filepath}".format(
                **_read_file(fs3, 'data/metadata/json-test.json')),
            "{checksum} {filepath}".format(
                **_read_file(fs3, 'data/filenames.txt')),
        ])),
        ('data/filenames.txt', set([
            '{0} foobar.txt'.format(file1_fn),
            '{0} foobar2.txt'.format(file2_fn),
            '{0} foobar3.txt'.format(file3_fn),
        ])),
        ('bag-info.txt', (
            "Source-Organization: European Organization for Nuclear Research\n"
            "Organization-Address: CERN, CH-1211 Geneva 23, Switzerland\n"
            "Bagging-Date: {0}\n".format(dt) +
            "Payload-Oxum: 236.6\n"
            "External-Identifier: {0}/SIPBagIt-v1.0.0\n".format(sips[2].id) +
            "External-Description: BagIt archive of SIP."
        )),
    ]
    for fs, expected in [(fs1, expected_sip1),
                         (fs2, expected_sip2),
                         (fs3, expected_sip3)]:
        for fn, exp_content in expected:
            with fs.open(fn) as fp:
                if isinstance(exp_content, set):
                    content = set(fp.read().splitlines())
                else:
                    content = fp.read()
            assert content == exp_content
