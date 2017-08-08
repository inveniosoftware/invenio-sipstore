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

from __future__ import absolute_import, print_function, unicode_literals

from uuid import UUID

from invenio_sipstore.archivers.utils import \
    secure_sipfile_name_formatter as fmt
from invenio_sipstore.archivers.utils import chunks, \
    default_archive_directory_builder
from invenio_sipstore.models import SIP


def test_chunks():
    """Test the chunk creation utility function."""
    assert list(chunks('123456', 2)) == ['12', '34', '56']
    assert list(chunks('1234567', 2)) == ['12', '34', '56', '7']
    assert list(chunks('1234567', [1, 2, 3])) == \
        ['1', '23', '456', '7']
    assert list(chunks('123', [1, 2, 3, 4])) == \
        ['1', '23']
    assert list(chunks('1234567', [1, ])) == \
        ['1', '234567']
    assert list(chunks('12', [1, 1, 1])) == \
        ['1', '2']
    assert list(chunks('1', [1, 1, 1])) == \
        ['1', ]


def test_default_archive_directory_builder(app, db):
    """Test the default archive builder."""
    sip_id = UUID('abcd0000-1111-2222-3333-444455556666')
    sip = SIP.create(id_=sip_id)
    assert default_archive_directory_builder(sip) == \
        ['ab', 'cd', '0000-1111-2222-3333-444455556666']


def test_secure_sipfilename_formatter(app, db):
    """Test some potentially dangerous or incompatible SIPFile filepaths."""
    class MockSIPFile(object):
        def __init__(self, file_id, filepath):
            self.file_id = file_id
            self.filepath = filepath
    sip_id = UUID('abcd0000-1111-2222-3333-444455556666')
    examples = [
        ('../../foobar.txt', 'foobar.txt'),
        ('/etc/shadow', 'etc_shadow'),
        ('łóżźćęą', 'ozzcea'),
        ('你好，世界', ''),
        ('مرحبا بالعالم', ''),
        ('𝓺𝓾𝓲𝓬𝓴 𝓫𝓻𝓸𝔀𝓷 𝓯𝓸𝔁 𝓳𝓾𝓶𝓹𝓼 𝓸𝓿𝓮𝓻 𝓽𝓱𝓮 𝓵𝓪𝔃𝔂 𝓭𝓸𝓰',
         'quick_brown_fox_jumps_over_the_lazy_dog'),
        ('ftp://testing.url.com', 'ftp_testing.url.com'),
        ('https://łóżźć.url.com', 'https_ozzc.url.com'),
        ('.dotfile', 'dotfile'),
        ('$PATH', 'PATH'),
        ('./a/regular/nested/file.txt', 'a_regular_nested_file.txt'),
        ('Name with spaces.txt', 'Name_with_spaces.txt'),
    ]
    for orig, secure in examples:
        assert fmt(MockSIPFile(sip_id, orig)) == \
            "{0}-{1}".format(sip_id, secure)
