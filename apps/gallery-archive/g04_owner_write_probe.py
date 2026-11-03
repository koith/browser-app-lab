#!/usr/bin/env python3
"""Isolated real-owner TeraBox JPEG + WebP write/readback QA.

Synthetic fixture bytes are never put into the owner catalog or gallery.
No existing photo is changed. A pass requires independent full SHA readback.
"""
import argparse
import hashlib
from io import BytesIO
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from PIL import Image, ImageDraw

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'apps/mimmi-gallery/cloud/gateway'))
from cookie_format import cookie_header

REMOTES={'mimmi':'archive:MimmiArchive','yui':'archive:YuiArchive'}


def cmd(args,timeout=80):
    try:
        return subprocess.run(['rclone',*args,'--timeout=60s','--retries=1'],
                              stdout=subprocess.PIPE,stderr=subprocess.PIPE,
                              timeout=timeout,check=False)
    except subprocess.TimeoutExpired:
        print('G04_REMOTE_PROBE_TIMEOUT',args[0],flush=True)
        return None


def image_bytes(seed,preview=False):
    im=Image.new('RGB',(420,420),'#e4e1df')
    pen=ImageDraw.Draw(im)
    for i in range(16):
        d=hashlib.sha256((seed+str(i)).encode()).digest()
        x=int.from_bytes(d[:2],'big')%355
        y=int.from_bytes(d[2:4],'big')%355
        pen.rectangle((x,y,x+45,y+45),fill=tuple(40+v%175 for v in d[4:7]))
    if preview:im.thumbnail((160,160))
    output=BytesIO()
    im.save(output,format='WEBP' if preview else 'JPEG',
            quality=79 if preview else 93)
    return output.getvalue()


def exact_read(remote,key,expected,destination):
    stream=cmd(['cat',remote+'/'+key])
    if stream is not None and stream.returncode==0 and stream.stdout==expected:
        return 'cat'
    alt=cmd(['copyto',remote+'/'+key,str(destination),'--ignore-times'])
    if alt is not None and alt.returncode==0 and destination.is_file():
        if destination.read_bytes()==expected:return 'copyto'
    return None


def main(model,run_id):
    if model not in REMOTES or not run_id.isdigit() or len(run_id)>25:
        raise ValueError('Invalid exact owner QA scope')
    raw=os.environ.get('MIMMI_COOKIE' if model=='mimmi' else 'YUI_COOKIE','')
    header=cookie_header(raw)
    if not header:raise ValueError('Existing owner session unavailable')
    os.environ['RCLONE_CONFIG_ARCHIVE_COOKIE']=header
    from owner_upload_web_token import update_current_process
    try:
        update_current_process()
        print('G04_NORMAL_OWNER_WEB_UPLOAD_STATE',model,True,flush=True)
    except Exception as e:
        if type(e).__name__ not in ('WebStateUnavailable','RequestError',
                                    'ReadTimeout','ConnectTimeout','ConnectError',
                                    'TimeoutException','OSError'):
            raise
        print('G04_NORMAL_OWNER_WEB_STATE_UNAVAILABLE',model,
              type(e).__name__,'EXACT_SHA_STILL_REQUIRED',True,flush=True)
    remote=REMOTES[model]
    verified=[]
    with tempfile.TemporaryDirectory(prefix='g04-sha-') as directory:
        root=Path(directory)
        for variant,ext in (('original','jpg'),('preview','webp')):
            raw=image_bytes(run_id+model,variant=='preview')
            digest=hashlib.sha256(raw).hexdigest()
            # Never use an actual gallery original/preview or index path.
            key=f'metadata/g04-physical-qa/{model}/{run_id}/{digest}.{ext}'
            local=root/(variant+'.'+ext)
            local.write_bytes(raw)
            put=cmd(['copyto',str(local),remote+'/'+key,'--ignore-existing'])
            transport=exact_read(remote,key,raw,root/(variant+'-readback.bin'))
            print('G04_OWNER_PHYSICAL_OBJECT',model,variant,
                  'UPLOAD_RC',put.returncode if put else 'timeout',
                  'SHA256_VERIFIED',bool(transport),
                  'READ_METHOD',transport or 'none',flush=True)
            if not transport:
                print('G04_OWNER_STORAGE_TEST_NOT_VERIFIED',model,
                      'GALLERY_PHOTOS_ADDED',0,flush=True)
                return False
            verified.append(key)
        for key in verified:
            assert key.startswith(f'metadata/g04-physical-qa/{model}/{run_id}/')
            removed=cmd(['deletefile',remote+'/'+key])
            print('G04_PROBE_OWN_FIXTURE_CLEANUP',model,
                  'SUCCESS',bool(removed and removed.returncode==0),flush=True)
    print('G04_ORIGINAL_PREVIEW_REAL_REMOTE_SHA_PASS',model,
          'MEDIA_OBJECTS',len(verified),'GALLERY_PHOTOS_ADDED',0,flush=True)
    return True


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--model',choices=['mimmi','yui'],required=True)
    parser.add_argument('--run-id',required=True)
    args=parser.parse_args()
    sys.exit(0 if main(args.model,args.run_id) else 1)
