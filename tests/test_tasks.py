# -*- coding: utf-8 -*-
#
# This file is part of Invenio.
# Copyright (C) 2016 CERN.
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


"""Module tests."""

from __future__ import absolute_import, print_function

import hashlib
from os import listdir, path

from invenio_sipstore.tasks import archive_sip


def calculate_md5(filename):
    """Calculate the MD5 of the content of a file."""
    with open(filename) as fp:
        return hashlib.md5(fp.read().encode('utf-8')).hexdigest()


def test_task_bagit_file_generation(tmp_archive_path_task, sip_with_file):
    """Test sending a security message using Task module."""
    archive_sip(sip_with_file.id)

    dir = path.join(tmp_archive_path_task, str(sip_with_file.id),
                    sip_with_file.archived_at.isoformat())

    root_content = listdir(dir)
    assert 'bagit.txt' in root_content
    assert 'bag-info.txt' in root_content
    assert 'tagmanifest-md5.txt' in root_content
    assert 'manifest-md5.txt' in root_content

    assert len(listdir(path.join(dir, 'data', 'files'))) == 1


def test_task_bagit_file_generation_bagit_txt(tmp_archive_path_task, task_app,
                                              sip_with_file):
    """Test of bagit.txt content."""
    archive_sip(sip_with_file.id)

    filename = path.join(tmp_archive_path_task, str(sip_with_file.id),
                         sip_with_file.archived_at.isoformat(),
                         'bagit.txt')

    with open(filename) as fp:
        content_items = fp.read().splitlines()
        len(content_items) >= 2
        assert 'BagIt-Version: ' in content_items[0]
        assert 'Tag-File-Character-Encoding: ' in content_items[1]


def test_task_bagit_file_generation_baginfo_txt(tmp_archive_path_task,
                                                task_app, sip_with_file):
    """Test of bagit.txt content."""
    archive_sip(sip_with_file.id)

    filename = path.join(tmp_archive_path_task, str(sip_with_file.id),
                         sip_with_file.archived_at.isoformat(),
                         'bag-info.txt')

    with open(filename) as fp:
        content_items = fp.read().splitlines()
        assert len(content_items) >= 1
        assert any(i.startswith('Bagging-Date: ') for i in content_items)
        assert any(i.startswith('Payload-Oxum: ') for i in content_items)


def test_task_bagit_file_generation_manifest_txt(tmp_archive_path_task,
                                                 sip_with_file):
    """Test of manigest-md5.txt."""
    archive_sip(sip_with_file.id)
    base_path = path.join(tmp_archive_path_task, str(sip_with_file.id),
                          sip_with_file.archived_at.isoformat())
    filename = path.join(base_path, 'manifest-md5.txt')

    with open(filename) as fp:
        content_items = fp.read().splitlines()
        assert len(content_items) >= 1
        for item in content_items:
            separator = item.find(' ')
            file_md5 = item[:separator]
            file_filename = item[separator + 1:]
            assert file_md5 == calculate_md5(
                path.join(base_path, file_filename))


def test_task_bagit_file_generation_tag_manifest_txt(tmp_archive_path_task,
                                                     sip_with_file):
    """Test of tagmanigest-md5.txt."""
    archive_sip(sip_with_file.id)
    base_path = path.join(tmp_archive_path_task, str(sip_with_file.id),
                          sip_with_file.archived_at.isoformat())
    filename = path.join(base_path, 'tagmanifest-md5.txt')

    with open(filename) as fp:
        content_items = fp.read().splitlines()
        assert len(content_items) == 3
        for item in content_items:
            separator = item.find(' ')
            file_md5 = item[:separator]
            file_filename = item[separator + 1:]
            assert file_md5 == calculate_md5(
                path.join(base_path, file_filename))
