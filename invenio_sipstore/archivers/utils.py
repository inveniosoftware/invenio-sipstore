# -*- coding: utf-8 -*-
#
# This file is part of Invenio.
# Copyright (C) 2017-2019 CERN.
# Copyright (C) 2024 TU Wien.
#
# Invenio is free software; you can redistribute it and/or modify it
# under the terms of the MIT License; see LICENSE file for more details.

"""Utilities for SIPStore archivers."""

from werkzeug.utils import secure_filename


def _secure_filename(filename):
    """Call ``secure_filename()`` and replace dashes with underscores."""
    return secure_filename(filename).replace("-", "_")


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
            yield iterable[i : i + n]
    elif isinstance(n, list):
        acc = 0
        if sum(n) < len(iterable):
            n.append(len(iterable))
        for i in n:
            if acc < len(iterable):
                yield iterable[acc : acc + i]
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
    return list(
        chunks(
            str(sip.id),
            [
                2,
                2,
            ],
        )
    )


def default_sipmetadata_name_formatter(sipmetadata):
    """Default generator for the SIPMetadata filenames."""
    return f"{sipmetadata.type.name}.{sipmetadata.type.format}"


def simple_sipfile_name_formatter(sipfile):
    """Simple generator the SIPFile filenames.

    Keeps the original filename for the file in the archive.
    Writes the file in the archive under the original filename.

    WARNING: This can potentially cause security and portability issues if
    the SIPFile filenames come from the users.
    """
    return sipfile.filepath


def secure_sipfile_name_formatter(sipfile):
    """Secure filename generator for the SIPFiles.

    Since the filenames can be potentially dangerous, incompatible
    with the underlying file system, or not portable across operating systems
    this formatter uses :py:func:`werkzeug.utils.secure_filename` to replace
    potentially problematic parts in the filename (like UNIX directory navigation:
    ".", "..", "/", etc.).
    For more information on the ``secure_filename`` function visit:
    ``http://werkzeug.pocoo.org/docs/utils/#werkzeug.utils.secure_filename``
    Additionally, dashes are replaced with underscores.

    Since this operation alone could result in name collisions with "sibling"
    SIPFiles (the ones that are linked to the same SIP), their names are also
    calculated and checked.
    In case of a detected collision, the resulting filenames are numbered
    (based on their ID, which ensures reproducibility).
    """
    filename = _secure_filename(sipfile.filepath)
    siblings = sorted(sipfile.sip.sip_files, key=lambda sf: sf.file_id)
    colliding_siblings = [
        sf for sf in siblings if _secure_filename(sf.filepath) == filename
    ]

    if len(colliding_siblings) > 1:
        # at least one other SIPFile would receive the same result, so we add
        # numbering to avoid the collision
        # note: since we replace dashes with underscores in ``_secure_filename()``,
        #       this operation cannot create new collisions
        return f"{colliding_siblings.index(sipfile) + 1}-{filename}"

    else:
        # no collision detected
        return filename or "-"


def secure_uuid_sipfile_name_formatter(sipfile):
    """Secure and collision-resistant filename generator for the SIPFiles.

    This is very similar to :py:func:`secure_sipfile_name_formatter` in that it
    uses :py:func:`werkzeug.utils.secure_filename`.
    In contrast to the other function, it will use the file's UUID as prefix
    to avoid naming conflicts however.
    This eliminates the necessity to have a look at the "sibling" SIPFiles,
    but will result in longer and more cluttered filenames.
    """
    return f"{sipfile.file_id}-{secure_filename(sipfile.filepath)}"
