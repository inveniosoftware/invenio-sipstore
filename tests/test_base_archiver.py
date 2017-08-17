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

from __future__ import absolute_import, print_function, unicode_literals

from hashlib import md5

from invenio_sipstore.archivers import BaseArchiver


def test_getters(db, sips, sip_metadata_types, locations):
    """Test the constructor and the getters."""
    sip = sips[0]
    archiver = BaseArchiver(sip)
    assert archiver._get_archive_base_uri() == locations['archive'].uri
    assert archiver.sip is sip
    # get data files
    data_files_info = archiver._get_data_files()
    sip_id = str(sip.id)
    abs_path_fmt = "{root}/{c1}/{c2}/{cn}/".format(
        root=locations['archive'].uri, c1=sip_id[:2], c2=sip_id[2: 4],
        cn=sip_id[4:]) + "{filepath}"
    abs_path = abs_path_fmt.format(filepath="files/foobar.txt")
    fi = {
        'file_uuid': str(sip.files[0].file_id),
        'filepath': 'files/foobar.txt',
        'filename': 'foobar.txt',
        'sipfilepath': 'foobar.txt',
        'size': 4,
        'fullpath': abs_path,
        'checksum': 'md5:098f6bcd4621d373cade4e832627b4f6'
    }
    assert data_files_info == [fi, ]

    metafiles_info = archiver._get_metadata_files()
    assert len(metafiles_info) == 2
    m1_abs_path = abs_path_fmt.format(filepath="metadata/json-test.json")
    m2_abs_path = abs_path_fmt.format(
        filepath="metadata/marcxml-test.xml")
    m1 = {
        'checksum': 'md5:da4ab7e4c4b762d8e2f3ec3b9f801b1f',
        'fullpath': m1_abs_path,
        'metadata_id': sip_metadata_types['json-test'].id,
        'filepath': 'metadata/json-test.json',
        'size': 19
    }
    m2 = {
        'checksum': 'md5:498d1ce86c2e9b9eb85f1e8105affdf6',
        'fullpath': m2_abs_path,
        'metadata_id': sip_metadata_types['marcxml-test'].id,
        'filepath': 'metadata/marcxml-test.xml',
        'size': 12
    }
    assert m1 in metafiles_info
    assert m2 in metafiles_info

    all_files_info = archiver.get_all_files()
    assert len(all_files_info) == 3
    assert fi in all_files_info
    assert m1 in all_files_info
    assert m2 in all_files_info


def test_write(db, sips, sip_metadata_types, locations, archive_fs):
    """Test writing of the SIPFiles and SIPMetadata files to archive."""
    sip = sips[0]
    archiver = BaseArchiver(sip)
    data_files_info = archiver._get_data_files()
    assert not archive_fs.listdir()  # Empty archive
    archiver._write_sipfile(data_files_info[0])
    assert len(archive_fs.listdir()) == 1
    fs = archive_fs.opendir(archiver._get_archive_subpath())
    assert fs.isfile('files/foobar.txt')

    assert not fs.isfile('metadata/json-test.json')
    assert not fs.isfile('metadata/marcxml-test.xml')
    metadata_files_info = archiver._get_metadata_files()
    archiver._write_sipmetadata(metadata_files_info[0])
    archiver._write_sipmetadata(metadata_files_info[1])
    assert fs.isfile('metadata/json-test.json')
    assert fs.isfile('metadata/marcxml-test.xml')

    assert not fs.isfile('test.txt')
    archiver._write_extra(content='test raw content', filename='test.txt')
    assert fs.isfile('test.txt')
    with fs.open('test.txt', 'r') as fp:
        cnt = fp.read()
    assert cnt == 'test raw content'

    assert not fs.isfile('test2.txt')
    extra_file_info = dict(
        checksum=('md5:' + str(md5('test'.encode('utf-8')).hexdigest())),
        size=len('test'),
        filepath='test2.txt',
        fullpath=fs.getsyspath('test2.txt'),
        content='test'
    )
    archiver._write_extra(fileinfo=extra_file_info)
    assert fs.isfile('test.txt')
    with fs.open('test.txt', 'r') as fp:
        cnt = fp.read()
    assert cnt == 'test raw content'


def test_write_all(db, sips, sip_metadata_types, locations, archive_fs):
    """Test the public "write_all_files" method."""
    sip = sips[0]
    archiver = BaseArchiver(sip)
    assert not archive_fs.listdir()
    archiver.write_all_files()
    assert len(archive_fs.listdir()) == 1
    fs = archive_fs.opendir(archiver._get_archive_subpath())
    assert len(fs.listdir()) == 2
    assert len(fs.listdir('metadata')) == 2
    assert len(fs.listdir('files')) == 1
    expected = {
            ('metadata/marcxml-test.xml', '<p>XML 1</p>'),
            ('metadata/json-test.json', '{"title": "JSON 1"}'),
            ('files/foobar.txt', 'test'),
    }
    for fn, content in expected:
        with fs.open(fn, 'r') as fp:
            c = fp.read()
        assert c == content


def test_name_formatters(db, app, sips, sip_metadata_types, locations,
                         archive_fs, secure_sipfile_name_formatter,
                         custom_sipmetadata_name_formatter):
    """Test archiving with custom filename formatter."""
    sip = sips[3]  # SIP with some naughty filenames
    archiver = BaseArchiver(sip, filenames_mapping_file='files/filenames.txt')
    assert not archive_fs.listdir()
    archiver.write_all_files()
    assert len(archive_fs.listdir()) == 1
    fs = archive_fs.opendir(archiver._get_archive_subpath())
    assert set(fs.listdir()) == set(['metadata', 'files'])
    assert len(fs.listdir('metadata')) == 2
    # inside 'files/' there should be 'filenames.txt' file with the mappings
    assert len(fs.listdir('files')) == 4
    uuid1 = next(f.file.id for f in sip.files if f.filepath.endswith('txt'))
    uuid2 = next(f.file.id for f in sip.files if f.filepath.endswith('js'))
    uuid3 = next(f.file.id for f in sip.files if f.filepath.endswith('dat'))
    expected = [
            ('metadata/marcxml-test-metadata.xml', '<p>XML 4 żółć</p>'),
            ('metadata/json-test-metadata.json', '{"title": "JSON 4 żółć"}'),
            ('files/{0}-foobar.txt'.format(uuid1), 'test-fourth żółć'),
            ('files/{0}-http_maliciouswebsite.com_hack.js'.format(uuid2),
             'test-fifth ąęćźə'),
            ('files/{0}-ozzcae.dat'.format(uuid3), 'test-sixth π'),
            ('files/filenames.txt',
             set(['{0}-foobar.txt ../../foobar.txt'.format(uuid1),
                  '{0}-http_maliciouswebsite.com_hack.js '
                  'http://maliciouswebsite.com/hack.js'.format(uuid2),
                  '{0}-ozzcae.dat łóżźćąę.dat'.format(uuid3), ]))

    ]
    for fn, content in expected:
        with fs.open(fn, 'r') as fp:
            if isinstance(content, set):  # Compare as set of lines
                c = set(fp.read().splitlines())
            else:
                c = fp.read()
        assert c == content
