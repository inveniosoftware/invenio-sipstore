# -*- coding: utf-8 -*-
#
# This file is part of Invenio.
# Copyright (C) 2016-2019 CERN.
# Copyright (C) 2024 TU Wien.
#
# Invenio is free software; you can redistribute it and/or modify it
# under the terms of the MIT License; see LICENSE file for more details.

"""Module tests for the BagItArchiver class."""

from uuid import UUID

from invenio_sipstore.archivers.utils import (
    chunks,
    default_archive_directory_builder,
    secure_sipfile_name_formatter,
    secure_uuid_sipfile_name_formatter,
)
from invenio_sipstore.models import SIP


def test_chunks():
    """Test the chunk creation utility function."""
    assert list(chunks("123456", 2)) == ["12", "34", "56"]
    assert list(chunks("1234567", 2)) == ["12", "34", "56", "7"]
    assert list(chunks("1234567", [1, 2, 3])) == ["1", "23", "456", "7"]
    assert list(chunks("123", [1, 2, 3, 4])) == ["1", "23"]
    assert list(
        chunks(
            "1234567",
            [
                1,
            ],
        )
    ) == ["1", "234567"]
    assert list(chunks("12", [1, 1, 1])) == ["1", "2"]
    assert list(chunks("1", [1, 1, 1])) == [
        "1",
    ]


def test_default_archive_directory_builder(app, db):
    """Test the default archive builder."""
    sip_id = UUID("abcd0000-1111-2222-3333-444455556666")
    sip = SIP.create(id_=sip_id)
    assert default_archive_directory_builder(sip) == [
        "ab",
        "cd",
        "0000-1111-2222-3333-444455556666",
    ]


def test_secure_uuid_sipfilename_formatter(app, db):
    """Test some potentially dangerous or incompatible SIPFile filepaths."""

    class MockSIPFile:
        def __init__(self, file_id, filepath):
            self.file_id = file_id
            self.filepath = filepath

    sip_id = UUID("abcd0000-1111-2222-3333-444455556666")
    examples = [
        ("../../foobar.txt", "foobar.txt"),
        ("/etc/shadow", "etc_shadow"),
        ("łóżźćęą", "ozzcea"),
        ("1-", "1-"),
        ("你好，世界", ""),
        ("مرحبا بالعالم", ""),
        (
            "𝓺𝓾𝓲𝓬𝓴 𝓫𝓻𝓸𝔀𝓷 𝓯𝓸𝔁 𝓳𝓾𝓶𝓹𝓼 𝓸𝓿𝓮𝓻 𝓽𝓱𝓮 𝓵𝓪𝔃𝔂 𝓭𝓸𝓰",
            "quick_brown_fox_jumps_over_the_lazy_dog",
        ),
        ("ftp://testing.url.com", "ftp_testing.url.com"),
        ("https://łóżźć.url.com", "https_ozzc.url.com"),
        (".dotfile", "dotfile"),
        ("$PATH", "PATH"),
        ("./a/regular/nested/file.txt", "a_regular_nested_file.txt"),
        ("Name with spaces.txt", "Name_with_spaces.txt"),
    ]
    for orig, secure in examples:
        formatted_name = secure_uuid_sipfile_name_formatter(MockSIPFile(sip_id, orig))
        assert formatted_name == f"{sip_id}-{secure}"


def test_secure_sipfilename_formatter(app, db):
    """Test some potentially dangerous or incompatible SIPFile filepaths."""

    class MockSIP:
        def __init__(self, sip_files=None):
            self.sip_files = sip_files or []

    class MockSIPFile:
        def __init__(self, file_id, filepath, sip):
            self.file_id = file_id
            self.filepath = filepath
            self.sip = sip
            self.sip.sip_files.append(self)

    examples = [
        ("../../foobar.txt", "foobar.txt"),
        ("/etc/shadow", "etc_shadow"),
        ("łóżźćęą", "ozzcea"),
        ("1-", "1_"),
        ("你好，世界", "1-"),
        ("مرحبا بالعالم", "2-"),
        (
            "𝓺𝓾𝓲𝓬𝓴 𝓫𝓻𝓸𝔀𝓷 𝓯𝓸𝔁 𝓳𝓾𝓶𝓹𝓼 𝓸𝓿𝓮𝓻 𝓽𝓱𝓮 𝓵𝓪𝔃𝔂 𝓭𝓸𝓰",
            "quick_brown_fox_jumps_over_the_lazy_dog",
        ),
        ("ftp://testing.url.com", "ftp_testing.url.com"),
        ("https://łóżźć.url.com", "https_ozzc.url.com"),
        (".dotfile", "1-dotfile"),
        ("dotfile", "2-dotfile"),
        ("$PATH", "PATH"),
        ("./a/regular/nested/file.txt", "a_regular_nested_file.txt"),
        ("Name with spaces.txt", "Name_with_spaces.txt"),
    ]

    sip = MockSIP()
    sip_files = [
        (MockSIPFile(id_, fp, sip=sip), efp) for (id_, (fp, efp)) in enumerate(examples)
    ]

    # try formatting some SIPFile names, including some that would cause collisions
    for sip_file, expected_result in sip_files:
        formatted_name = secure_sipfile_name_formatter(sip_file)
        assert formatted_name == expected_result

    # try an empty filename
    sip_file = MockSIPFile(0, "", sip=MockSIP())
    assert secure_sipfile_name_formatter(sip_file) == "-"
