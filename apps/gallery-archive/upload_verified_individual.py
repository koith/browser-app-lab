"""Upload verified gallery photos one pair at a time, with partial success.

A remote file is accepted only after an authenticated, exact SHA-256 readback.
Unlike a directory-wide rclone copy, one missing preview or rejected original
must not hide other completely verified works/photos. Never alter the live
catalogue when no new photo pair passed. Never overwrite a different file.
"""
from __future__ import annotations

import argparse
from collections import Counter
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import time

from defer_verified_batch import checked
from merge_incremental import checked_row
from safe_rclone import run
from verify_terabox import read_remote_with_recovery

REMOTES={'yui':'archive:YuiArchive','mimmi':'archive:MimmiArchive'}


def _verified_local(stage, path, sha, size, dimensions=None, ext=None):
    file=(stage/path).resolve()
    if not file.is_relative_to(stage.resolve()) or not file.is_file():
        raise ValueError('Staged original or preview absent')
    raw,actual_dimensions,actual_extension=checked(file,sha,size)
    if dimensions is not None and actual_dimensions!=dimensions:
        raise ValueError('Staged original dimensions differ from catalog')
    if ext is not None and actual_extension!=ext:
        raise ValueError('Staged preview has wrong format')
    return file


def _read_exact(remote, row, readback):
    try:
        return readback(row,remote)==row[0]
    except (ValueError,OSError,TimeoutError):
        return False


def _upload_one(src, row, remote, uploader, readback, sleep):
    """One write, independent full-byte SHA; retry only transient missing object.

    Do not repeatedly retry an authentication/challenge error (400141). A
    successful write response is NOT a verified object without SHA readback.
    """
    key,size,sha=row
    if _read_exact(remote,row,readback):
        return 'already_verified'
    args=['copyto',str(src),remote+'/'+key,'--ignore-existing',
          '--timeout=15s','--retries=1','--low-level-retries=1']
    rc=uploader(args)
    if rc:
        # A partial response from the provider can occur after a successful
        # write. Exact readback is the only acceptable recovery evidence.
        return 'written_despite_error' if _read_exact(remote,row,readback) else 'upload_rejected'
    for i in range(3):
        if _read_exact(remote,row,readback):
            return 'newly_verified'
        if i<2:
            sleep(2**i)
    return 'remote_byte_readback_unavailable'


def persist_new_photos(stage, previous, remote, model, uploader=run,
                       readback=read_remote_with_recovery, sleep=time.sleep):
    stage,previous=Path(stage),Path(previous)
    if model not in REMOTES or remote!=REMOTES[model]:
        raise ValueError('Wrong owner archive remote')
    current_path=stage/'metadata/catalog.json'
    current=json.loads(current_path.read_text(encoding='utf-8'))
    old=json.loads(previous.read_text(encoding='utf-8'))
    if (old.get('model')!=model or current.get('model')!=model
            or old.get('schema_version')!=1 or current.get('schema_version')!=1):
        raise ValueError('Owner catalog model/schema mismatch')
    existing={a['id']:a for a in old['albums']}
    new_catalog=deepcopy(old)
    by_id={a['id']:a for a in new_catalog['albums']}
    attempts=0;accepted=[];failed=[];statuses=Counter()
    held_local=[]
    for album in current['albums']:
        aid=album['id']
        old_slots={p['number']:p for p in existing.get(aid,{}).get('images',[])}
        for photo in album['images']:
            checked_row(model,aid,photo)
            original_path=stage/photo['key']
            preview_path=stage/photo['preview'] if photo.get('preview') else None
            # A pre-existing, remotely indexed original has no local staging.
            if not original_path.is_file() and not (
                    preview_path is not None and preview_path.is_file()):
                continue
            attempts+=1
            if not original_path.is_file() or preview_path is None or not preview_path.is_file():
                raise ValueError('Incomplete locally staged photo pair')
            if (photo['number'] in old_slots and
                    old_slots[photo['number']]['sha256']==photo['sha256']):
                continue
            if photo['number'] in old_slots and not photo.get('higher_visual_quality_replacement'):
                raise ValueError('Photo slot replacement without optical evidence')
            original=_verified_local(stage,photo['key'],photo['sha256'],
                                     photo['bytes'],(photo['width'],photo['height']))
            preview=_verified_local(stage,photo['preview'],photo['preview_sha256'],
                                    photo['preview_bytes'],ext='webp')
            outcomes=[]
            for local,field,hashkey,byteskey in (
                    (original,'key','sha256','bytes'),
                    (preview,'preview','preview_sha256','preview_bytes')):
                row=(photo[field],photo[byteskey],photo[hashkey])
                status=_upload_one(local,row,remote,uploader,readback,sleep)
                outcomes.append(status)
                statuses[status]+=1
                if status not in ('already_verified','newly_verified','written_despite_error'):
                    break
            if len(outcomes)==2 and all(o in (
                    'already_verified','newly_verified','written_despite_error') for o in outcomes):
                if aid not in by_id:
                    src_title=album.get('title') or aid
                    item={'id':aid,'title':src_title,'expected':None,
                          'complete':False,'images':[]}
                    by_id[aid]=item;new_catalog['albums'].append(item)
                row=deepcopy(photo)
                current_album=by_id[aid]
                current_album['images']=[p for p in current_album['images']
                                         if p['number']!=row['number']]+[row]
                current_album['images'].sort(key=lambda p:p['number'])
                accepted.append({'id':aid,'number':row['number'],
                                 'sha256':row['sha256']})
            else:
                failed.append({'id':aid,'number':photo['number'],
                               'reason':outcomes[-1] if outcomes else 'missing_pair'})
                held_local.extend([original,preview])
    # Exclude failed local files from the subsequent strict --only-staged read.
    # They were fully validated locally, but still CANNOT reach the owner index.
    for local in held_local:
        local.unlink(missing_ok=True)
    before=sum(len(a['images']) for a in old['albums'])
    additions=sum(1 for row in accepted if row['number'] not in {
        p['number'] for p in existing.get(row['id'],{}).get('images',[])})
    upgrades=len(accepted)-additions
    after=sum(len(a['images']) for a in new_catalog['albums'])
    if after!=before+additions:
        raise ValueError('Incremental verified owner catalog does not reconcile')
    new_catalog['storage']='owner-private-terabox-sha-verified-bytes'
    new_catalog['summary']={
        'physical_photo_positions':after,'albums':len(new_catalog['albums']),
        'new_photo_slots_this_import':additions,
        'higher_resolution_replacements':upgrades,
        'previous_photos_retained':before}
    report={'model':model,'new_photo_candidates':attempts,
            'new_photo_pairs_sha_verified':len(accepted),
            'failed_photo_pairs':len(failed),
            'new_photos':additions,'upgraded_photos':upgrades,
            'previous_photos':before,'total_photos':after,
            'per_file_statuses':dict(statuses),
            'held_failure_reasons':dict(Counter(f['reason'] for f in failed)),
            'verification':'original_AND_preview_exact_remote_SHA256',
            'partial_success_without_unverified_publication':True}
    metadata=stage/'metadata'
    (metadata/'per-file-upload-report.json').write_text(
        json.dumps({**report,'accepted':accepted,'held':failed},
                   ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print('OWNER_VERIFIED_INDIVIDUAL_UPLOAD',json.dumps(report,ensure_ascii=False),flush=True)
    if not accepted:
        if attempts:
            raise ValueError('No independently verified original/preview pairs; owner unchanged')
        return report
    current_path.write_text(
        json.dumps(new_catalog,ensure_ascii=False,separators=(',',':'))+'\n',
        encoding='utf-8')
    (metadata/'incremental-merge.json').write_text(
        json.dumps({'model':model,'new_photos':additions,
                    'upgraded_photos':upgrades,'previous_photos':before,
                    'total_photos':after,
                    'verified_new_pairs':len(accepted),
                    'held_failed_pairs':len(failed)},
                   ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    return report


if __name__=='__main__':
    p=argparse.ArgumentParser()
    p.add_argument('--stage',type=Path,required=True)
    p.add_argument('--previous',type=Path,required=True)
    p.add_argument('--remote',required=True)
    p.add_argument('--model',choices=sorted(REMOTES),required=True)
    a=p.parse_args()
    persist_new_photos(a.stage,a.previous,a.remote,a.model)
