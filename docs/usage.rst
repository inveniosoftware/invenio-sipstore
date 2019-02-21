..
    This file is part of Invenio.
    Copyright (C) 2016-2019 CERN.

    Invenio is free software; you can redistribute it and/or modify it
    under the terms of the MIT License; see LICENSE file for more details.


Prerequisites
=============

 1. Create a location for the SIPs with the name 'archive'.


Usage
=====

.. automodule:: invenio_sipstore

1. On your service create a SIP representing what you want to archive

    - It can contain files
    - It can contain metadata


2. Create a record with files

    .. code:: python
       recid = uuid.uuid4()
       pid = PersistentIdentifier.create('recid', '1501', object_type='rec',
                                         object_uuid=recid,
                                         status=PIDStatus.REGISTERED)
       record = Record.create({'$schema': 'https://zenodo.org/schemas/deposits/records/record-v1.0.0.json',
                               '_deposit': {'status': 'draft'},
                               'title': 'demo'},
                              recid)
       record.commit()
       db.session.commit()
       # put a file in the record
       stream = BytesIO(b'head crab\n')
       b = Bucket.create()
       RecordsBuckets.create(bucket=b, record=record.model)
       db.session.commit()
       record.files['crab.txt'] = stream
       record.files.dumps()
       record.commit()
       db.session.commit()

    The created record must have the key ``$schema`` with the same value as
    the metadata type’s schema.

    Here, we have created a simple record with the following metadata:

    .. code:: json
       {
           "$schema": "https://zenodo.org/schemas/deposits/records/record-v1.0.0.json",
           "_deposit": {
               "status": "draft"
           },
           "title": "demo"
       }
    It also contains one file ``crab.txt`` that contains the words
    ``head crab``.


3. Create the SIP

    .. code:: python
        sip = RecordSIP.create(pid, record, True, user_id=1)
        db.session.commit()

    If you want to patch a SIP fetch the previous created sip if any

    .. code:: python
        sip_patch_of = (
                db.session.query(SIP)
                .join(RecordSIP, RecordSIP.sip_id == SIP.id)
                .filter(RecordSIP.pid_id == sip_recid.id)
                .order_by(SIPM.created.desc())
                .first()
            )

4. Create the archiver and bagit

    .. code:: python
        archiver = BagItArchiver(
                sip.sip, include_all_previous=True,
                patch_of=sip_patch_of)

    Set include_all_previous to  True or False if it is the first time you create a bagit or you patch a previous one.

    .. code:: python
        archiver.save_bagit_metadata()

5. Send the SIP for archiving

    Fetch the already created SIP

    .. code:: python
         sip = (
            RecordSIP.query
            .filter_by(pid_id=recid.id)
            .order_by(RecordSIP.created.desc())
            .first().sip
        )

    Trigger the task for archiving it

    .. code:: python
        archive_sip.delay(str(sip.id))

    The task should look like this
    
    .. code:: python
        from invenio_sipstore.api import SIP as SIPApi
        from invenio_sipstore.models import SIP as SIPModel

        @shared_task(ignore_result=True, max_retries=6,
             default_retry_delay=4 * 60 * 60)
        def archive_sip(sip_uuid):
            try:
                sip = SIPApi(SIPModel.query.get(sip_uuid))
                archiver = BagItArchiver(sip)
                bagmeta = archiver.get_bagit_metadata(sip)
                if bagmeta is None:
                    raise ArchivingError(
                        'Bagit metadata does not exist for SIP: {0}.'.format(sip.id))
                if sip.archived:
                    raise ArchivingError(
                        'SIP was already archived {0}.'.format(sip.id))
                archiver.write_all_files()
                sip.archived = True
                db.session.commit()
            except Exception as exc:
                # On ArchivingError (see above), do not retry, but re-raise
                if not isinstance(exc, ArchivingError):
                    archive_sip.retry(exc=exc)
                raise