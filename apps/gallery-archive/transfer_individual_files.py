"""Transfer existing, decoded original files without bundles or account secrets.

Private plans, paths and ephemeral signing keys must stay outside the public
repository. Only a public verification key and an expiring manifest fingerprint
are configured on the existing owner gateway.
"""
import argparse
import base64
from concurrent.futures import ThreadPoolExecutor,as_completed
import hashlib
from io import BytesIO
import json
import os
from pathlib import Path
import time
from urllib.parse import urlsplit

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import Encoding,PrivateFormat,PublicFormat,NoEncryption,load_pem_private_key
from PIL import Image
import requests

ROOT=Path(__file__).resolve().parents[2]


def checked(path,sha,size):
    data=path.read_bytes()
    if len(data)!=size or hashlib.sha256(data).hexdigest()!=sha:raise ValueError('Existing individual file changed')
    with Image.open(BytesIO(data)) as im:im.verify()
    with Image.open(BytesIO(data)) as im:
        im.load();return data,im.size,{'JPEG':'jpg','PNG':'png','WEBP':'webp'}[im.format]


def prepare(args):
    out=args.out.resolve()
    if out.is_relative_to(ROOT):raise ValueError('Private transfer plans and keys must remain outside the public repository')
    out.mkdir(parents=True,exist_ok=True,mode=0o700)
    owner=json.loads(args.owner.read_text());model=owner['model']
    old={a['id']:a for a in owner['albums']};seen={p['sha256'] for a in old.values() for p in a['images']}
    groups={};files={}
    for metadata in args.metadata:
        doc=json.loads(metadata.read_text())
        albums=[doc['work']] if 'work' in doc and doc['work'] else doc.get('albums',[])
        root=metadata.parent.parent if metadata.parent.name=='metadata' else metadata.parent
        audits=[doc['info']] if 'info' in doc else []
        auditfile=root/'metadata/collection-audit.json'
        if auditfile.exists():audits+=json.loads(auditfile.read_text()).get('results',[])
        coverage={a['id']:a for a in audits if 'id' in a}
        for album in albums:
            aid=album['id']
            if aid not in old:raise ValueError('Transfers may only supplement existing owner works')
            for p in album['images']:
                if p['sha256'] in seen:continue
                if p.get('higher_resolution_replacement') or p.get('work_identity_saved_cut_anchors',0)<3:
                    raise ValueError('Only already-confirmed new cuts belong to this transfer')
                original=(root/p['key']).resolve();preview=(root/p['preview']).resolve()
                if not original.is_relative_to(root.resolve()) or not preview.is_relative_to(root.resolve()):
                    raise ValueError('Unsafe original-file path')
                _,size,ext=checked(original,p['sha256'],p['bytes'])
                _,thumb,thumbext=checked(preview,p['preview_sha256'],p['preview_bytes'])
                if size!=(p['width'],p['height']) or thumbext!='webp':raise ValueError('Wrong declared image variant')
                row={k:p[k] for k in ('sha256','bytes','width','height','preview_sha256','preview_bytes',
                    'source_photo_number','work_identity_saved_cut_anchors')}
                row.update(extension=ext,preview_width=thumb[0],preview_height=thumb[1])
                evidence={k:v for k,v in coverage.get(aid,{}).items() if k in (
                    'source','known_web_edition_photos','observed_filename_numbers','saved_cut_correspondence',
                    'uncertain_source_numbers','unresolved_source_numbers','source_files_decoded',
                    'source_edition_all_files_decoded','source_edition_all_files_accounted_for')}
                groups.setdefault(aid,{'id':aid,'title':old[aid].get('title',aid),
                    'source_coverage':evidence,'images':[]})['images'].append(row)
                files[p['sha256']]=str(original);files[p['preview_sha256']]=str(preview);seen.add(p['sha256'])
    plan={'schema_version':1,'model':model,'expires_at':int(time.time())+6*3600,'albums':list(groups.values())}
    raw=(json.dumps(plan,ensure_ascii=False,sort_keys=True,separators=(',',':'))+'\n').encode()
    pin=hashlib.sha256(raw).hexdigest();(out/'manifest.json').write_bytes(raw)
    (out/'files.json').write_text(json.dumps(files,ensure_ascii=False,indent=2)+'\n')
    keyfile=out/'operator-private.pem'
    if keyfile.exists():private=load_pem_private_key(keyfile.read_bytes(),password=None)
    else:
        private=Ed25519PrivateKey.generate()
        descriptor=os.open(keyfile,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
        with os.fdopen(descriptor,'wb') as stream:
            stream.write(private.private_bytes(Encoding.PEM,PrivateFormat.PKCS8,NoEncryption()))
    public=base64.b64encode(private.public_key().public_bytes(Encoding.Raw,PublicFormat.Raw)).decode()
    config={'ARCHIVE_IMPORT_PUBLIC_KEY':public,'ARCHIVE_IMPORT_MANIFEST_SHA256':pin}
    (out/'public-verification-config.json').write_text(json.dumps(config)+'\n')
    print('VERIFIED_LOCAL_TRANSFER_PLAN',model,'works',len(groups),'photos',sum(len(a['images']) for a in groups.values()),
          'individual_objects',len(files),'REMOTE_NEW_PHOTOS',0,'GALLERY_NEW_PHOTOS',0,flush=True)


def gateway_client(root,origin):
    if origin!='https://mimmi-private-gallery-free.onrender.com':
        raise ValueError('Only the existing user archive gateway is supported')
    raw=(root/'manifest.json').read_bytes();pin=hashlib.sha256(raw).hexdigest()
    plan=json.loads(raw)
    if time.time()>=plan['expires_at']:raise ValueError('The exact transfer permit expired')
    private=load_pem_private_key((root/'operator-private.pem').read_bytes(),password=None)
    def request(method,path,body):
        digest=hashlib.sha256(body).hexdigest();stamp=str(int(time.time()))
        message='\n'.join((method,path,pin,stamp,digest)).encode()
        headers={'x-archive-time':stamp,'x-archive-body-sha256':digest,
                 'x-archive-signature':base64.b64encode(private.sign(message)).decode(),
                 'content-type':'application/octet-stream','content-length':str(len(body))}
        response=requests.request(method,origin+path,data=body,headers=headers,timeout=(12,210),allow_redirects=False)
        if response.status_code!=200:
            raise RuntimeError('Individual-file operation failed: HTTP '+str(response.status_code)+' '+response.text[:180])
        return response.json()
    return request,raw


def connection_state(args):
    request,raw=gateway_client(args.plan,args.origin)
    request('POST','/internal/individual-import/manifest',raw)
    result=request('POST','/internal/individual-import/connection-state',b'')
    path=args.plan/'sealed-connection-private.json'
    descriptor=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_TRUNC,0o600)
    with os.fdopen(descriptor,'w') as out:json.dump(result,out)
    print('ENCRYPTED_OWNER_RESTART_STATE_PREPARED','PLAINTEXT_CREDENTIAL_EXPORTED',False,flush=True)


def upload(args):
    root=args.plan;request,raw=gateway_client(root,args.origin)
    files=json.loads((root/'files.json').read_text())
    request('POST','/internal/individual-import/manifest',raw)
    def send(item):
        sha,path=item;body=Path(path).read_bytes()
        if hashlib.sha256(body).hexdigest()!=sha:raise ValueError('Private staged photo changed before transfer')
        reply=request('PUT','/internal/individual-import/file/'+sha,body)
        if not reply.get('remote_sha256_verified'):raise ValueError('No remote original readback acknowledgement')
        return sha,reply
    count=0
    workers=ThreadPoolExecutor(max_workers=2)
    futures=[workers.submit(send,item) for item in files.items()]
    try:
        with (root/'remote-object-receipts.jsonl').open('a') as receipts:
            for future in as_completed(futures):
                sha,reply=future.result();count+=1
                receipts.write(json.dumps({'sha256':sha,**reply})+'\n');receipts.flush()
                if count%20==0 or count==len(files):print('ACTUAL_REMOTE_INDIVIDUAL_READBACK',count,'/',len(files),flush=True)
    finally:
        # An access/transport failure stops queued writes. Do not repeat the
        # same failing storage operation for hundreds of remaining objects.
        workers.shutdown(wait=True,cancel_futures=True)
    final=request('POST','/internal/individual-import/finish',b'')
    (root/'pending-transfer-result.json').write_text(json.dumps(final,indent=2)+'\n')
    print('REMOTE_INDIVIDUAL_BYTES_TRANSFERRED',final['remote_verified_photos'],
          'OWNER_CATALOG_PUBLISHED',False,'GALLERY_OPEN_VERIFIED',False,flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser();sub=p.add_subparsers(dest='mode',required=True)
    a=sub.add_parser('prepare');a.add_argument('--owner',type=Path,required=True)
    a.add_argument('--metadata',type=Path,nargs='+',required=True);a.add_argument('--out',type=Path,required=True)
    for action in ('upload','connection-state'):
        a=sub.add_parser(action);a.add_argument('--plan',type=Path,required=True)
        a.add_argument('--origin',default='https://mimmi-private-gallery-free.onrender.com')
    args=p.parse_args();{'prepare':prepare,'upload':upload,'connection-state':connection_state}[args.mode](args)
