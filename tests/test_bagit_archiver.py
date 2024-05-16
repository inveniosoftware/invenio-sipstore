# -*- coding: utf-8 -*-
#
# This file is part of Invenio.
# Copyright (C) 2016-2019 CERN.
# Copyright (C) 2024 TU Wien.
#
# Invenio is free software; you can redistribute it and/or modify it
# under the terms of the MIT License; see LICENSE file for more details.

"""Module tests for the BagItArchiver class."""

import hashlib
import json
from datetime import datetime

import pytest

from invenio_sipstore.api import SIP as SIPApi
from invenio_sipstore.archivers.bagit_archiver import BagItArchiver
from invenio_sipstore.archivers.base_archiver import BaseArchiver


def fetch_file_endswith(sip, filename_suffix):
    """A helper method for fetching SIPFiles by the name suffix."""
    return next(f for f in sip.files if f.filepath.endswith(filename_suffix))


def test_constructor(sips):
    """Test the archiver constructor."""
    s = BaseArchiver(sips[0].model).sip
    s2 = BaseArchiver(sips[0]).sip
    assert isinstance(s, SIPApi)
    assert isinstance(s2, SIPApi)

    a = BagItArchiver(sips[1], patch_of=sips[0])
    a2 = BagItArchiver(sips[1].model, patch_of=sips[0].model)
    assert isinstance(a.sip, SIPApi)
    assert isinstance(a.patch_of, SIPApi)
    assert isinstance(a2.sip, SIPApi)
    assert isinstance(a2.patch_of, SIPApi)


def test_get_all_files(sips):
    """Test the function get_all_files."""
    archiver = BagItArchiver(sips[0])
    files = archiver.get_all_files()
    assert len(files) == 9


@pytest.mark.parametrize(
    "hash_alg",
    [("MD5", "md5"), ("SHA-1", "sha1"), ("sha-256", "sha256"), ("sha-512", "sha512")],
)
def test_write_all_files(sips, archive_fs, hash_alg):
    """Test the creation and export of a SIP with various hash algorithms."""
    sip = sips[0]
    hash_alg, hash_alg_norm = hash_alg
    archiver = BagItArchiver(
        sip, hash_algorithm=hash_alg, filenames_mapping_file="data/filenames.json"
    )
    assert not len(archive_fs.listdir("."))
    archiver.write_all_files()
    assert len(archive_fs.listdir(".")) == 1
    fs = archive_fs.opendir(archiver.get_archive_subpath())

    # check if all expected files are there
    assert set(fs.listdir(".")) == set(
        [
            f"tagmanifest-{hash_alg_norm}.txt",
            "bagit.txt",
            f"manifest-{hash_alg_norm}.txt",
            "bag-info.txt",
            "data",
        ]
    )
    assert set(fs.listdir("data")) == set(["metadata", "files", "filenames.json"])
    assert set(fs.listdir("data/metadata")) == set(
        ["marcxml-test.xml", "json-test.json", "txt-test.txt"]
    )
    assert set(fs.listdir("data/files")) == set(
        [
            "foobar.txt",
        ]
    )

    # check if the specified hashes are valid too
    with fs.open(f"manifest-{hash_alg_norm}.txt") as manifest_file:
        for line in manifest_file:
            expected_checksum, filename = line.rstrip().split(" ", 1)
            with fs.open(filename, "rb") as data_file:
                hash = hashlib.new(hash_alg, data=data_file.read())
                assert hash.hexdigest() == expected_checksum

    with fs.open(f"tagmanifest-{hash_alg_norm}.txt") as tagmanifest_file:
        for line in tagmanifest_file:
            expected_checksum, filename = line.rstrip().split(" ", 1)
            with fs.open(filename, "rb") as tag_file:
                hash = hashlib.new(hash_alg, data=tag_file.read())
                assert hash.hexdigest() == expected_checksum


def test_save_bagit_metadata(sips):
    """Test saving of bagit metadata."""
    sip = sips[0]
    assert not BagItArchiver.get_bagit_metadata(sip)
    archiver = BagItArchiver(sip)
    archiver.save_bagit_metadata()
    bmeta = BagItArchiver.get_bagit_metadata(sip, as_dict=True)
    file_m = next(f for f in bmeta["files"] if "sipfilepath" in f)
    assert file_m["sipfilepath"] == "foobar.txt"
    assert file_m["filepath"] == "data/files/foobar.txt"

    sip.model.sip_files[0].filepath = "changed.txt"
    with pytest.raises(Exception) as excinfo:
        archiver.save_bagit_metadata()
    assert "Attempting to save" in str(excinfo.value)
    archiver.save_bagit_metadata(overwrite=True)
    bmeta = BagItArchiver.get_bagit_metadata(sip, as_dict=True)

    file_m = next(f for f in bmeta["files"] if "sipfilepath" in f)
    assert file_m["sipfilepath"] == "changed.txt"
    assert file_m["filepath"] == "data/files/changed.txt"


def _read_file(fs, filepath):
    with fs.open(filepath, "r") as fp:
        content = fp.read()
    return {
        "checksum": hashlib.md5(content.encode("utf-8")).hexdigest(),
        "size": len(content),
        "filepath": filepath,
    }


def test_write_patched(mocker, sips, archive_fs, secure_uuid_sipfile_name_formatter):
    """Test the BagIt archiving with previous SIP as a base."""
    # Mock the bagging date generation so the 'Bagging-Date' tag is predefined
    dt = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S.%f")
    mocker.patch(
        "invenio_sipstore.archivers.bagit_archiver.BagItArchiver."
        "_generate_bagging_date",
        return_value=dt,
    )

    arch1 = BagItArchiver(sips[0], filenames_mapping_file="data/filenames.json")
    arch1.write_all_files()
    arch2 = BagItArchiver(
        sips[1], patch_of=sips[0], filenames_mapping_file="data/filenames.json"
    )
    arch2.write_all_files()
    arch3 = BagItArchiver(
        sips[2],
        patch_of=sips[1],
        include_all_previous=True,
        filenames_mapping_file="data/filenames.json",
    )
    arch3.write_all_files()
    arch5 = BagItArchiver(
        sips[4],
        patch_of=sips[2],
        include_all_previous=True,
        filenames_mapping_file="data/filenames.json",
    )
    arch5.write_all_files()

    # NOTE: We take only SIP-1, SIP-2, SIP-3 and SIP-5.
    # Enumeration of related objects follows the "sips" fixture naming
    fs1 = archive_fs.opendir(arch1.get_archive_subpath())
    fs2 = archive_fs.opendir(arch2.get_archive_subpath())
    fs3 = archive_fs.opendir(arch3.get_archive_subpath())
    fs5 = archive_fs.opendir(arch5.get_archive_subpath())
    assert len(fs1.listdir(".")) == 5
    assert len(fs2.listdir(".")) == 6  # Includes 'fetch.txt'
    assert len(fs3.listdir(".")) == 6  # Includes 'fetch.txt'
    assert len(fs5.listdir(".")) == 6  # Includes 'fetch.txt'

    # Check SIP-1,2,3,5 data contents
    assert set(fs1.listdir("data")) == set(["files", "metadata", "filenames.json"])
    assert len(fs1.listdir("data/files")) == 1
    assert len(fs1.listdir("data/metadata")) == 3

    assert set(fs2.listdir("data")) == set(["files", "metadata", "filenames.json"])
    assert len(fs2.listdir("data/files")) == 1
    assert len(fs2.listdir("data/metadata")) == 2

    assert set(fs3.listdir("data")) == set(["files", "metadata", "filenames.json"])
    assert len(fs3.listdir("data/files")) == 1
    assert len(fs3.listdir("data/metadata")) == 2

    assert set(fs5.listdir("data")) == set(["metadata", "filenames.json"])
    assert len(fs5.listdir("data/metadata")) == 1

    # Fetch the filenames for easier fixture formatting below
    file1_fn = f"{fetch_file_endswith(sips[0], 'foobar.txt').file_id}-foobar.txt"
    file2_fn = f"{fetch_file_endswith(sips[1], 'foobar2.txt').file_id}-foobar2.txt"
    file3_fn = f"{fetch_file_endswith(sips[2], 'foobar3.txt').file_id}-foobar3.txt"
    file2_rn_fn = f"{fetch_file_endswith(sips[2], 'foobar2-renamed.txt').file_id}-foobar2-renamed.txt"  # noqa

    f1_dp = f"data/files/{file1_fn}"
    f2_dp = f"data/files/{file2_fn}"
    f3_dp = f"data/files/{file3_fn}"

    fn_map = {
        file1_fn: "foobar.txt",
        file2_fn: "foobar2.txt",
        file3_fn: "foobar3.txt",
    }

    assert file2_fn[:36] == file2_rn_fn[:36]
    # Both file2_fn and file2_rn_fn are referring to the same FileInstance,
    # so their UUID prefix should match
    expected_sip1 = [
        (f"data/files/{file1_fn}", "test"),
        ("data/metadata/marcxml-test.xml", "<p>XML 1</p>"),
        ("data/metadata/json-test.json", '{"title": "JSON 1"}'),
        ("bagit.txt", "BagIt-Version: 1.0\nTag-File-Character-Encoding: UTF-8\n"),
        (
            "manifest-md5.txt",
            set(
                [
                    "{checksum} {filepath}".format(
                        **_read_file(fs1, f"data/files/{file1_fn}")
                    ),
                    "{checksum} {filepath}".format(
                        **_read_file(fs1, "data/metadata/marcxml-test.xml")
                    ),
                    "{checksum} {filepath}".format(
                        **_read_file(fs1, "data/metadata/json-test.json")
                    ),
                    "{checksum} {filepath}".format(
                        **_read_file(fs1, "data/metadata/txt-test.txt")
                    ),
                    "{checksum} {filepath}".format(
                        **_read_file(fs1, "data/filenames.json")
                    ),
                ]
            ),
        ),
        (
            "data/filenames.json",
            json.dumps({file1_fn: "foobar.txt"}, indent=1),
        ),
        (
            "bag-info.txt",
            (
                "Source-Organization: European Organization for Nuclear Research\n"
                "Organization-Address: CERN, CH-1211 Geneva 23, Switzerland\n"
                f"Bagging-Date: {dt}\nPayload-Oxum: 115.5\n"
                f"External-Identifier: {sips[0].id}/SIPBagIt-v1.0.0\n"
                "External-Description: BagIt archive of SIP.\n"
                "X-Agent-Email: spiderpig@invenio.org\n"
                "X-Agent-Ip-Address: 1.1.1.1\n"
                "X-Agent-Orcid: 1111-1111-1111-1111\n"
            ),
        ),
    ]

    expected_sip2 = [
        (f"data/files/{file2_fn}", "test-second"),
        ("data/metadata/marcxml-test.xml", "<p>XML 2</p>"),
        ("data/metadata/json-test.json", '{"title": "JSON 2"}'),
        ("bagit.txt", "BagIt-Version: 1.0\nTag-File-Character-Encoding: UTF-8\n"),
        ("fetch.txt", set([f"{fs1.getsyspath(f1_dp)} 4 {f1_dp}"])),
        (
            "manifest-md5.txt",
            set(
                [
                    "{checksum} {filepath}".format(**_read_file(fs1, f1_dp)),
                    "{checksum} {filepath}".format(**_read_file(fs2, f2_dp)),
                    "{checksum} {filepath}".format(
                        **_read_file(fs2, "data/metadata/marcxml-test.xml")
                    ),
                    "{checksum} {filepath}".format(
                        **_read_file(fs2, "data/metadata/json-test.json")
                    ),
                    "{checksum} {filepath}".format(
                        **_read_file(fs2, "data/filenames.json")
                    ),
                ]
            ),
        ),
        (
            "data/filenames.json",
            json.dumps({k: fn_map[k] for k in sorted([file1_fn, file2_fn])}, indent=1),
        ),
        (
            "bag-info.txt",
            (
                "Source-Organization: European Organization for Nuclear Research\n"
                "Organization-Address: CERN, CH-1211 Geneva 23, Switzerland\n"
                f"Bagging-Date: {dt}\nPayload-Oxum: 182.5\n"
                f"External-Identifier: {sips[1].id}/SIPBagIt-v1.0.0\n"
                "External-Description: BagIt archive of SIP.\n"
            ),
        ),
    ]

    expected_sip3 = [
        (f"data/files/{file3_fn}", "test-third"),
        ("data/metadata/marcxml-test.xml", "<p>XML 3</p>"),
        ("data/metadata/json-test.json", '{"title": "JSON 3"}'),
        ("bagit.txt", "BagIt-Version: 1.0\nTag-File-Character-Encoding: UTF-8\n"),
        (
            "fetch.txt",
            set(
                [
                    f"{fs1.getsyspath(f1_dp)} 4 {f1_dp}",
                    # Explanation on entry below: The file is fetched using original
                    # filename (file2_fn) as it will be archived in SIP-2, however
                    # the new destination has the 'renamed' filename (file2_rn_fn).
                    # This is correct and expected behaviour
                    f"{fs2.getsyspath(f2_dp)} 11 data/files/{file2_rn_fn}",
                ]
            ),
        ),
        (
            "manifest-md5.txt",
            set(
                [
                    "{checksum} {filepath}".format(**_read_file(fs1, f1_dp)),
                    # Manifest also specifies the renamed filename for File-2
                    "{checksum} data/files/{newfilename}".format(
                        newfilename=file2_rn_fn, **_read_file(fs2, f2_dp)
                    ),
                    "{checksum} {filepath}".format(**_read_file(fs3, f3_dp)),
                    "{checksum} {filepath}".format(
                        **_read_file(fs3, "data/metadata/marcxml-test.xml")
                    ),
                    "{checksum} {filepath}".format(
                        **_read_file(fs3, "data/metadata/json-test.json")
                    ),
                    "{checksum} {filepath}".format(
                        **_read_file(fs3, "data/filenames.json")
                    ),
                ]
            ),
        ),
        (
            "data/filenames.json",
            json.dumps(
                {k: fn_map[k] for k in sorted([file1_fn, file2_fn, file3_fn])}, indent=1
            ),
        ),
        (
            "bag-info.txt",
            (
                "Source-Organization: European Organization for Nuclear Research\n"
                "Organization-Address: CERN, CH-1211 Geneva 23, Switzerland\n"
                f"Bagging-Date: {dt}\nPayload-Oxum: 260.6\n"
                f"External-Identifier: {sips[2].id}/SIPBagIt-v1.0.0\n"
                "External-Description: BagIt archive of SIP.\n"
            ),
        ),
    ]

    expected_sip5 = [
        ("data/metadata/marcxml-test.xml", "<p>XML 5 Meta Only</p>"),
        ("bagit.txt", "BagIt-Version: 1.0\nTag-File-Character-Encoding: UTF-8\n"),
        (
            "fetch.txt",
            set(
                [
                    f"{fs1.getsyspath(f1_dp)} 4 {f1_dp}",
                    # As in "expected_sip3" above, the file is fetched using original
                    # filename (file2_fn) as it will be archived in SIP-2, however
                    # the new destination has the 'renamed' filename (file2_rn_fn).
                    # This is correct and expected behaviour
                    f"{fs2.getsyspath(f2_dp)} 11 {f'data/files/{file2_rn_fn}'}",
                    f"{fs3.getsyspath(f3_dp)} 10 {f3_dp}",
                ]
            ),
        ),
        (
            "manifest-md5.txt",
            set(
                [
                    "{checksum} {filepath}".format(**_read_file(fs1, f1_dp)),
                    # Manifest also specifies the renamed filename for File-2
                    "{checksum} data/files/{newfilename}".format(
                        newfilename=file2_rn_fn, **_read_file(fs2, f2_dp)
                    ),
                    "{checksum} {filepath}".format(**_read_file(fs3, f3_dp)),
                    "{checksum} {filepath}".format(
                        **_read_file(fs5, "data/metadata/marcxml-test.xml")
                    ),
                    "{checksum} {filepath}".format(
                        **_read_file(fs5, "data/filenames.json")
                    ),
                ]
            ),
        ),
        (
            "data/filenames.json",
            json.dumps(
                {k: fn_map[k] for k in sorted([file1_fn, file2_fn, file3_fn])}, indent=1
            ),
        ),
        (
            "bag-info.txt",
            (
                "Source-Organization: European Organization for Nuclear Research\n"
                "Organization-Address: CERN, CH-1211 Geneva 23, Switzerland\n"
                f"Bagging-Date: {dt}\nPayload-Oxum: 251.5\n"
                f"External-Identifier: {sips[4].id}/SIPBagIt-v1.0.0\n"
                "External-Description: BagIt archive of SIP.\n"
            ),
        ),
    ]

    for fs, expected in [
        (fs1, expected_sip1),
        (fs2, expected_sip2),
        (fs3, expected_sip3),
        (fs5, expected_sip5),
    ]:
        for fn, exp_content in expected:
            with fs.open(fn) as fp:
                if isinstance(exp_content, set):
                    content = set(fp.read().splitlines())
                else:
                    content = fp.read()
            assert content == exp_content
