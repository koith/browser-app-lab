"""Verify already-uploaded originals using private metadata, never a live upload API.

The only image writes allowed here are separate lossless previews in the
existing private archive. Original bytes are READ ONLY and pinned beforehand.
"""
import base64
from concurrent.futures import ThreadPoolExecutor,as_completed
import hashlib
from io import BytesIO
import json
import os
from pathlib import Path
import time

import requests
from PIL import Image
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

from sealed_work_metadata import REPOSITORY,HEX,encode,unseal,validate
from read_owner_metadata import read as read_owner
from load_pending_individual import storage
from direct_photo_pipeline import inspect
from defer_verified_batch import prepare,persist
from safe_rclone import run as storage_write

ROOT=Path(__file__).resolve().parents[2]
REMOTE='archive:MimmiArchive'
RECIPIENT_PATH='apps/gallery-archive/verification/metadata-courier/recipient.json'
PAYLOAD_PATH='apps/gallery-archive/verification/metadata-courier/sealed.json'


def github(method,path,body=None,missing=False):
    response=requests.request(method,'https://api.github.com/repos/'+REPOSITORY+path,
        headers={'Authorization':'Bearer '+os.environ['GH_TOKEN'],'Accept':'application/vnd.github+json'},
        json=body,timeout=(12,30))
    if missing and response.status_code==404:return None
    if response.status_code not in (200,201,204):
        raise ValueError('Own-repository metadata exchange failed HTTP '+str(response.status_code))
    return response.json() if response.content else None


def exact_remote(key,size,digest):
    if not (key.startswith('originals/') or key.startswith('previews/')):
        raise ValueError('Only existing archive photo objects can be read')
    raw=storage(['cat',REMOTE+'/'+key],limit=size+1)
    if raw is None:return None
    if len(raw)!=size or hashlib.sha256(raw).hexdigest()!=digest:
        if len(raw)<=512:
            try:code=json.loads(raw).get('errno')
            except (ValueError,TypeError,AttributeError):code=None
            if type(code) is int:raise ValueError('Owner provider response instead of image; errno='+str(code))
        raise ValueError('Exact existing owner object SHA or length changed')
    return raw


def save(path,raw):
    path.parent.mkdir(parents=True,exist_ok=True)
    fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
    with os.fdopen(fd,'wb') as output:output.write(raw)


def restore_work(album,owner,stage):
    aid=album['id'];old=next(a for a in owner['albums'] if a['id']==aid)
    present={p['sha256'] for a in owner['albums'] for p in a['images']}
    requested=[p for p in sorted(album['images'],key=lambda p:p['source_photo_number']) if p['sha256'] not in present]
    if not requested:
        print('EXISTING_WORK_ALREADY_INDEXED_NO_NEW_FILES',aid,flush=True);return 0
    rows=[];specs=[]
    def check(p):
        # No operation in this worker uploads an original or changes its key.
        key=f"originals/{aid}/{p['sha256']}.{p['extension']}"
        raw=exact_remote(key,p['bytes'],p['sha256'])
        if raw is None:raise ValueError('Expected already-uploaded original is missing')
        meta,generated,_=inspect(raw)
        if (meta['width'],meta['height'])!=(p['width'],p['height']):
            raise ValueError('Existing original decoded dimensions changed')
        preview=f"previews/{aid}/{p['preview_sha256']}.webp"
        thumbnail=exact_remote(preview,p['preview_bytes'],p['preview_sha256'])
        if thumbnail is None:
            # A missing old encoder variant permits a new derived preview.
            # A denial/provider/integrity error above NEVER takes this path.
            preview_sha=hashlib.sha256(generated).hexdigest()
            preview=f'previews/{aid}/{preview_sha}.webp';thumbnail=generated
            local=stage/preview;save(local,thumbnail)
            if storage_write(['copyto',str(local),REMOTE+'/'+preview,'--ignore-existing',
                              '--timeout=60s','--retries=1']):raise ValueError('Private preview persistence failed')
            if exact_remote(preview,len(thumbnail),preview_sha)!=thumbnail:
                raise ValueError('Derived private preview failed exact remote readback')
        else:
            preview_sha=p['preview_sha256'];save(stage/preview,thumbnail)
        with Image.open(BytesIO(thumbnail)) as im:im.verify()
        with Image.open(BytesIO(thumbnail)) as im:
            im.load()
            if im.format!='WEBP' or not 1<=im.width<=p['width'] or not 1<=im.height<=p['height']:
                raise ValueError('Invalid separate preview')
        save(stage/key,raw)
        row={'sha256':p['sha256'],'bytes':p['bytes'],'width':p['width'],'height':p['height'],
            'key':key,'preview':preview,'preview_sha256':preview_sha,'preview_bytes':len(thumbnail),
            'source_photo_number':p['source_photo_number'],'source_numbering':'public_web_filename_not_publisher_original',
            'work_identity_saved_cut_anchors':p['work_identity_saved_cut_anchors'],'higher_resolution_replacement':False}
        return row
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures=[pool.submit(check,p) for p in requested]
        try:
            for future in as_completed(futures):
                rows.append(future.result())
                if len(rows)%20==0 or len(rows)==len(requested):
                    print('EXACT_EXISTING_PRIVATE_PHOTO_PAIRS_VERIFIED',aid,len(rows),'/',len(requested),flush=True)
        except BaseException:
            for future in futures:future.cancel()
            raise
    next_number=max(p['number'] for p in old['images'])+1
    for n,row in enumerate(sorted(rows,key=lambda p:p['source_photo_number']),next_number):row['number']=n
    evidence={**album['source_coverage'],'id':aid,'individual_files_saved':len(rows),
              'saved_reference_anchors':len({p['owner_sha256'] for p in album['source_coverage']['saved_cut_correspondence']})}
    metadata=stage/'metadata';metadata.mkdir(parents=True,exist_ok=True)
    (metadata/'catalog.json').write_bytes(encode({'schema_version':1,'model':'mimmi',
        'storage':'owner-private-terabox-sha-verified-bytes','albums':[{'id':aid,'title':old.get('title',aid),'images':rows}]}))
    (metadata/'collection-audit.json').write_bytes(encode({'model':'mimmi','results':[evidence],
        'new_local_individual_files':len(rows),'new_photo_positions':len(rows),'higher_resolution_replacements':0,
        'remote_verified_files':len(rows),'gallery_open_verified_files':0,'photo_bundles_created':0}))
    prepared=prepare(stage,owner)
    for a in prepared['albums']:
        for p in a['images']:
            specs.extend([(p['key'],p['bytes'],p['sha256']),(p['preview'],p['preview_bytes'],p['preview_sha256'])])
    fingerprint=hashlib.sha256(json.dumps(sorted(specs),separators=(',',':')).encode()).hexdigest()
    (metadata/'remote-verification.json').write_bytes(encode({'model':'mimmi','media_checked':len(specs),
        'full_SHA256_verified':len(specs),'failed':0,'photos':len(rows),'verified_specs_sha256':fingerprint,
        'scope':'every_exact_existing_remote_original_and_preview_read_this_workflow',
        'originals_uploaded':0,'live_catalog_changed':False}))
    persist(stage,REMOTE)
    return len(rows)


def main():
    os.umask(0o077)
    digest=os.environ['EXPECTED_METADATA_SHA256'];run_id=int(os.environ['GITHUB_RUN_ID'])
    attempt=int(os.environ['GITHUB_RUN_ATTEMPT'])
    if os.environ.get('GITHUB_REPOSITORY')!=REPOSITORY or not HEX.fullmatch(digest):
        raise ValueError('Only the same repository and exact predeclared metadata are allowed')
    branch=f'archive-metadata-{run_id}-{attempt}'
    private=rsa.generate_private_key(public_exponent=65537,key_size=2048)
    recipient={'schema_version':1,'repository':REPOSITORY,'model':'mimmi','run_id':run_id,'attempt':attempt,
        'metadata_sha256':digest,'public_key_pem':private.public_key().public_bytes(
            serialization.Encoding.PEM,serialization.PublicFormat.SubjectPublicKeyInfo).decode()}
    github('POST','/git/refs',{'ref':'refs/heads/'+branch,'sha':os.environ['GITHUB_SHA']})
    try:
        github('PUT','/contents/'+RECIPIENT_PATH,{'branch':branch,'message':'Publish ephemeral metadata-only recipient',
            'content':base64.b64encode(encode(recipient)).decode()})
        print('METADATA_ONLY_RECIPIENT_READY',branch,'EXPECTED_SHA',digest,'IMAGE_BYTES_ACCEPTED',False,flush=True)
        deadline=time.monotonic()+600;payload=None
        while time.monotonic()<deadline:
            payload=github('GET','/contents/'+PAYLOAD_PATH+'?ref='+branch,missing=True)
            if payload:break
            time.sleep(10)
        if not payload:raise TimeoutError('Bounded metadata-only handoff expired')
        if payload.get('size',0)>2800000:raise ValueError('Metadata envelope exceeds bounded size')
        envelope=json.loads(base64.b64decode(payload['content'],validate=False))
        data=unseal(envelope,recipient,private)
        raw=read_owner(REMOTE+'/metadata/catalog.json','mimmi',minimum=sum(len(a['images']) for a in
            json.loads((ROOT/'apps/mimmi-gallery/owner-index.json').read_text())['albums']))
        owner=json.loads(raw)
        reviewed={a['id']:a for a in json.loads((ROOT/'apps/mimmi-gallery/public-work-pages.json').read_text())['albums']}
        validate(data,owner,reviewed)
        total=0;failures=[]
        for album in data['albums']:
            stage=Path(os.environ['RUNNER_TEMP'])/'exact-existing-works'/album['id']
            try:total+=restore_work(album,owner,stage)
            except Exception as error:
                # Never print a private object path, provider payload or URL.
                message=str(error)
                safe=message if message.startswith(('Expected already-uploaded','Exact existing owner object',
                    'Owner provider response instead of image','Existing original decoded',
                    'Private preview persistence','Derived private preview','Invalid separate preview')) else 'Local validation or private storage operation failed'
                failures.append({'work':album['id'],'type':type(error).__name__,'cause':safe[:160]})
                print('EXISTING_WORK_HELD_NOT_QUEUED',album['id'],type(error).__name__,flush=True)
        print('EXISTING_PRIVATE_WORKS_QUEUED',total,'FAILED_WORKS',len(failures),
              'ORIGINAL_BYTES_UPLOADED',0,'LIVE_CATALOG_CHANGED',False,'GALLERY_QA_PASSED',False,flush=True)
        if failures:raise ValueError('One or more existing works failed strict verification: '+json.dumps(failures))
    finally:
        try:github('DELETE','/git/refs/heads/'+branch)
        except Exception:print('EPHEMERAL_METADATA_BRANCH_CLEANUP_PENDING',branch,flush=True)


if __name__=='__main__':main()
