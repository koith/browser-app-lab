"""Keep source correspondence in the SAME private archive before media transfer.

This is an unverified recovery journal, never an admission queue or live catalog.
It prevents a failed readback and an expired runner from orphaning uploaded bytes.
No metadata is sent to GitHub and no public/import permission is changed.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import time

from defer_verified_batch import checked,serialize
from load_pending_individual import storage
from merge_incremental import checked_row
from safe_rclone import run

REMOTES={'mimmi':'archive:MimmiArchive','yui':'archive:YuiArchive'}
STATE='unverified_private_recovery_journal_not_importable'


def snapshot(stage,model):
    catalog=json.loads((stage/'metadata/catalog.json').read_text())
    audit=json.loads((stage/'metadata/collection-audit.json').read_text())
    if catalog.get('model')!=model or catalog.get('schema_version')!=1 or audit.get('model')!=model:
        raise ValueError('Wrong private collection snapshot model')
    count=sum(len(a['images']) for a in catalog['albums'])
    if not count:return None,0
    if count>500:raise ValueError('Private collection snapshot exceeds bounded batch')
    seen=set()
    for album in catalog['albums']:
        aid=album['id']
        for photo in album['images']:
            identity=checked_row(model,aid,photo)
            if identity in seen:raise ValueError('Repeated collection slot')
            seen.add(identity)
            for key,digest,size,prefix in [('key','sha256','bytes','originals'),
                    ('preview','preview_sha256','preview_bytes','previews')]:
                path=photo[key]
                if not re.fullmatch(re.escape(prefix+'/'+aid+'/')+r'[a-z0-9.-]+',path):
                    raise ValueError('Unsafe collection object path')
                local=(stage/path).resolve()
                if not local.is_relative_to(stage.resolve()):raise ValueError('Unsafe collection staging file')
                _,dimensions,extension=checked(local,photo[digest],photo[size])
                if key=='key' and dimensions!=(photo['width'],photo['height']):
                    raise ValueError('Collected dimensions changed')
                if key=='preview' and extension!='webp':raise ValueError('Invalid collected preview format')
    raw=serialize({'schema_version':1,'model':model,'state':STATE,
        'remote_media_verified':False,'live_catalog_changed':False,
        'pending_admission_queue':False,'catalog':catalog,'collection_audit':audit})
    if len(raw)>2_000_000:raise ValueError('Private snapshot exceeds metadata size bound')
    return raw,count



def exact_journal_readback(stage,target,expected,attempts=4,sleep=time.sleep):
    """Independently verify newly uploaded private journal, with two read paths.

    The object can become readable only after metadata indexing completes.
    A mismatch is not proof of a missing file. Retry within a strict budget.
    If cat returns a provider JSON error but exits successfully, use rclone
    remote-to-local copyto as a second method. Never allow an unverified
    journal to unlock original-photo transfer.
    """
    if not 1<=attempts<=6:
        raise ValueError('Invalid exact journal readback budget')
    expected_hash=hashlib.sha256(expected).digest()
    reason='readback_not_attempted'
    scratch=stage/'metadata/unverified-collection-journal-readback.tmp'
    for n in range(attempts):
        if n:
            sleep(min(2**n,8))
        try:
            actual=storage(['cat',target],limit=len(expected)+1)
            if actual==expected:
                return 'remote_cat'
            reason='cat_missing_or_mismatched_bytes'
        except (OSError,TimeoutError,ValueError) as exc:
            reason='cat_'+type(exc).__name__
        try:
            if scratch.exists():
                scratch.unlink()
            code=run(['copyto',target,str(scratch),
                      '--timeout=60s','--retries=1'])
            if code==0 and scratch.is_file():
                if (scratch.stat().st_size==len(expected)
                        and hashlib.sha256(scratch.read_bytes()).digest()==expected_hash):
                    return 'remote_file_readback'
                reason='copyto_length_or_sha_mismatch'
            else:
                reason='copyto_unavailable_after_'+reason
        except (OSError,TimeoutError,ValueError) as exc:
            reason='copyto_'+type(exc).__name__
        finally:
            scratch.unlink(missing_ok=True)
    raise ValueError('Private source journal exact readback failed: '+reason)


def persist(stage,model,remote,run_key):
    if remote!=REMOTES[model] or not re.fullmatch(r'[1-9][0-9]{0,19}-[1-9][0-9]{0,5}',run_key):
        raise ValueError('Only the existing model archive and exact Actions run are allowed')
    raw,count=snapshot(stage,model)
    if raw is None:
        print('PRIVATE_UNVERIFIED_SOURCE_JOURNAL_NO_NEW_FILES',model,flush=True);return 0
    path=stage/'metadata/unverified-collection-snapshot.json'
    path.write_bytes(raw)
    # A distinct prefix and a non-batch filename keep this out of the normal
    # pending loader. This journal cannot make any photo eligible to publish.
    target=remote+'/metadata/unverified-collection-staging/'+run_key+'-'+model+'.json'
    if run(['copyto',str(path),target,'--ignore-existing','--timeout=60s','--retries=1']):
        raise ValueError('Private source journal storage failed before image transfer')
    method=exact_journal_readback(stage,target,raw)
    print('PRIVATE_UNVERIFIED_SOURCE_JOURNAL_PRESERVED',model,count,
          'READBACK_METHOD',method,
        'METADATA_SHA',hashlib.sha256(raw).hexdigest(),
        'MEDIA_VERIFIED',False,'GALLERY_PUBLISHED',False,flush=True)
    return count


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--stage',type=Path,required=True)
    p.add_argument('--model',choices=REMOTES,required=True);p.add_argument('--remote',required=True)
    p.add_argument('--run-key',required=True);a=p.parse_args()
    persist(a.stage,a.model,a.remote,a.run_key)
