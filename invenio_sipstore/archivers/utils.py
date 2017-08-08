# -*- coding: utf-8 -*-
#
# This file is part of Zenodo.
# Copyright (C) 2017 CERN.
#
# Zenodo is free software; you can redistribute it
# and/or modify it under the terms of the GNU General Public License as
# published by the Free Software Foundation; either version 2 of the
# License, or (at your option) any later version.
#
# Zenodo is distributed in the hope that it will be
# useful, but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Zenodo; if not, write to the
# Free Software Foundation, Inc., 59 Temple Place, Suite 330, Boston,
# MA 02111-1307, USA.
#
# In applying this license, CERN does not
# waive the privileges and immunities granted to it by virtue of its status
# as an Intergovernmental Organization or submit itself to any jurisdiction.

"""Utilities for SIPStore archivers."""

from __future__ import absolute_import, print_function

from werkzeug.utils import secure_filename


def chunks(iterable, n):
    """Yield iterable split into chunks.

    If 'n' is an integer, yield the iterable as n-sized chunks.
    If 'n' is a list of integers, yield chunks of sizes: n[0],
    n[1], ..., len(iterable) - sum(n)

    >>> from invenio_sipstore.archivers.utils import chunks
    >>> list(chunks('abcdefg', 3))
    ['abc', 'def', 'g']
    >>> list(chunks('abcdefg', [1, ]))
    ['a', 'bcdefg']
    >>> list(chunks('abcdefg', [1, 2, 3]))
    ['a', 'bc', 'def', 'g']
    """
    if isinstance(n, int):
        for i in range(0, len(iterable), n):
            yield iterable[i:i + n]
    elif isinstance(n, list):
        acc = 0
        if sum(n) < len(iterable):
            n.append(len(iterable))
        for i in n:
            if acc < len(iterable):
                yield iterable[acc: acc + i]
                acc += i


def default_archive_directory_builder(sip):
    """Build a directory structure for the archived SIP.

    Creates a structure that is based on the SIP's UUID.
    'abcdefgh-1234-1234-1234-1234567890ab' ->
    ['ab', 'cd', 'efgh-1234-1234-1234-1234567890ab']

    :param sip: SIP which is to be archived
    :type SIP: invenio_sipstore.models.SIP
    :returns: list of str
    """
    return list(chunks(str(sip.id), [2, 2, ]))


def default_sipmetadata_name_formatter(sipmetadata):
    """Default generator for the SIPMetadata filenames."""
    return "{name}.{format}".format(
        name=sipmetadata.type.name,
        format=sipmetadata.type.format
    )


def default_sipfile_name_formatter(sipfile):
    """Default generator the SIPFile filenames.

    Writes doen the file in the archive under the original filename.

    WARNING: This can potentially cause security and portability issues if
    the SIPFile filenames come from the users.
    """
    return sipfile.filepath


def secure_sipfile_name_formatter(sipfile):
    """Secure filename generator for the SIPFiles.

    Since the filenames can be potentially dangerous, not compatible
    with the underlying file system, or not portable across operating systems
    this formatter writes the files as a generic name: UUID-<secure_filename>,
    where <secure_filename> is the original filename which was stripped from
    any malicious parts (UNIX directory
    navigation '.', '..', '/'), special protocol parts ('ftp://', 'http://'),
    special device names on Windows systems, etc. and for maximum portability
    contains only ASCII characters.
    Since this operation can cause name collisions, the UUID of the
    underlying FileInstance is appended as prefix of the filename.
    For more information on the ``secure_filename`` function visit:
    ``http://werkzeug.pocoo.org/docs/utils/#werkzeug.utils.secure_filename``
    """
    return "{uuid}-{name}".format(
        uuid=str(sipfile.file_id),
        name=secure_filename(sipfile.filepath)
    )
