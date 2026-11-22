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
import os
import re
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


def durable_pair_checkpoint(stage, remote, model, run_key, album, row,
                            uploader=run, reader=None):
    """Persist a verified pair receipt in the existing private owner storage.

    This records a successful transfer, not permission to publish a photo.
    Original and preview bytes must already have passed independent SHA reads.
    Each receipt is immutable, so a runner death cannot erase earlier receipts.
    """
    if remote!=REMOTES.get(model) or not re.fullmatch(r'[1-9][0-9]{0,19}-[1-9][0-9]{0,5}',run_key):
        raise ValueError('Invalid private upload checkpoint scope')
    checked_row(model,album['id'],row)
    document={'schema_version':1,'model':model,'run':run_key,
              'scope':'verified_existing_pair_receipt_not_admission',
              'album':album['id'],'title':album.get('title') or album['id'],
              'photo':row,'remote_original_and_preview_sha_verified':True}
    raw=(json.dumps(document,ensure_ascii=False,sort_keys=True,separators=(',',':'))+'\n').encode()
    digest=hashlib.sha256(raw).hexdigest()
    path=stage/'metadata'/'verified-pair-checkpoints'/(digest+'.json')
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_bytes(raw)
    target=remote+'/metadata/verified-pair-checkpoints/'+run_key+'-'+model+'/'+digest+'.json'
    if reader is None:
        from private_collection_snapshot import exact_journal_readback
        reader=exact_journal_readback
    rc=uploader(['copyto',str(path),target,'--ignore-existing','--timeout=45s','--retries=1'])
    reader(stage,target,raw)
    print('PRIVATE_VERIFIED_PAIR_CHECKPOINT_STORED',model,'write_exit',rc,flush=True)
    return digest


def persist_new_photos(stage, previous, remote, model, uploader=run,
                       readback=read_remote_with_recovery, sleep=time.sleep,
                       checkpoint=None, stop_before=None):
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
    # Only the real authenticated owner client needs web-state refresh. Tests
    # inject an uploader and never touch a live session. The same helper is
    # used by the already deployed private Render gateway.
    refresh_owner_state=None
    if uploader is run:
        from owner_upload_web_token import update_current_process
        refresh_owner_state=update_current_process
    held_local=[]
    checkpointed=0
    stopped_for_budget=False
    consecutive_provider_rejections=0
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
            if refresh_owner_state is not None and attempts%30==1:
                from owner_upload_web_token import WebStateUnavailable
                import httpx
                try:
                    refresh_owner_state()
                    print('OWNER_UPLOAD_TOKEN_REFRESHED_DURING_BATCH',model,
                          'photo_attempt',attempts,flush=True)
                except (WebStateUnavailable,httpx.RequestError,TimeoutError) as exc:
                    # An optional token refresh cannot disable the existing
                    # cookie-authenticated path that already SHA-verified a
                    # real owner image. No alternative authentication is used.
                    print('OWNER_WEB_TOKEN_REFRESH_UNAVAILABLE',type(exc).__name__,
                          'OWNER_COOKIE_ONLY_PATH_REQUIRES_EXACT_SHA',True,flush=True)
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
            if stopped_for_budget or (stop_before is not None and stop_before()):
                stopped_for_budget=True
                failed.append({'id':aid,'number':photo['number'],'reason':'time_budget_reserved_for_commit'})
                held_local.extend([original,preview])
                continue
            if consecutive_provider_rejections>=3:
                failed.append({'id':aid,'number':photo['number'],
                               'reason':'provider_writes_paused_after_three_rejections'})
                held_local.extend([original,preview])
                statuses['provider_write_circuit_open']+=1
                continue
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
                # A completed pair is checkpointed before starting another.
                # If this cannot be saved, stop rather than accumulate orphaned work.
                if checkpoint is not None:
                    try:
                        checkpoint(album,row)
                        checkpointed+=1
                    except (ValueError,OSError,TimeoutError) as error:
                        print('PRIVATE_PAIR_CHECKPOINT_FAILED',type(error).__name__,flush=True)
                        stopped_for_budget=True
                consecutive_provider_rejections=0
            else:
                failed.append({'id':aid,'number':photo['number'],
                               'reason':outcomes[-1] if outcomes else 'missing_pair'})
                held_local.extend([original,preview])
                if 'upload_rejected' in outcomes:
                    consecutive_provider_rejections+=1
                else:
                    consecutive_provider_rejections=0
    # Keep failed, locally validated bytes out of the live staging manifest
    # without deleting them. The existing private metadata journal is not
    # a backup of bytes; this quarantine survives until runner cleanup only.
    # Never publish these files without independent remote SHA verification.
    for local in held_local:
        held = stage / 'held-upload-files' / local.relative_to(stage.resolve())
        held.parent.mkdir(parents=True, exist_ok=True)
        if held.exists():
            if held.read_bytes() != local.read_bytes():
                raise ValueError('Held upload path collision')
            local.unlink()
        else:
            local.replace(held)
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
            'durable_pair_checkpoints':checkpointed,
            'stopped_to_preserve_commit_budget':stopped_for_budget,
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
    run_id=os.environ.get('GITHUB_RUN_ID','')
    attempt=os.environ.get('GITHUB_RUN_ATTEMPT','')
    checkpoint=None
    if run_id and attempt:
        checkpoint=lambda album,row:durable_pair_checkpoint(
            a.stage,a.remote,a.model,run_id+'-'+attempt,album,row)
    stop_epoch=float(os.environ.get('GALLERY_UPLOAD_STOP_EPOCH','0'))
    # 12 minutes are reserved for the next pair's bounded IO plus its receipt;
    # the workflow reserves additional time for final verification/catalog.
    stop_before=(lambda:time.time()+720>=stop_epoch) if stop_epoch else None
    persist_new_photos(a.stage,a.previous,a.remote,a.model,
                       checkpoint=checkpoint,stop_before=stop_before)
