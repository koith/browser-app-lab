"""Short-lived, exact-manifest individual-file transfer to the existing archive.

No storage credential leaves this server. No archive container, public original,
catalogue overwrite, or public upload UI. The normal Actions transaction later
re-verifies the remote objects and publishes its merged owner catalogue.
"""
import asyncio
import base64
import hashlib
from io import BytesIO
import json
import os
from pathlib import Path
import re
import tempfile
import time

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
from fastapi import HTTPException, Request
from PIL import Image

SHA=re.compile(r'[a-f0-9]{64}\Z')
ALBUM=re.compile(r'[a-z0-9][a-z0-9-]{1,100}\Z')


class IndividualImport:
    def __init__(self,catalog,put,read,root=None,state_provider=None):
        self.catalog,self.put,self.read=catalog,put,read
        self.root=Path(root or tempfile.gettempdir())/'gallery-individual-import'
        self.plan=None;self.objects={};self.verified=set();self.locks={}
        self.workers=asyncio.Semaphore(2)
        self.state_provider=state_provider

    def authorize(self,request):
        pin=os.environ.get('ARCHIVE_IMPORT_MANIFEST_SHA256','')
        key=os.environ.get('ARCHIVE_IMPORT_PUBLIC_KEY','')
        if not SHA.fullmatch(pin) or not key:
            raise HTTPException(404,'Individual transfer is not configured')
        stamp=request.headers.get('x-archive-time','')
        digest=request.headers.get('x-archive-body-sha256','')
        try:
            if not stamp.isdigit() or abs(time.time()-int(stamp))>120 or not SHA.fullmatch(digest):
                raise ValueError()
            message='\n'.join((request.method,request.url.path,pin,stamp,digest)).encode()
            Ed25519PublicKey.from_public_bytes(base64.b64decode(key,validate=True)).verify(
                base64.b64decode(request.headers.get('x-archive-signature',''),validate=True),message)
        except Exception:
            raise HTTPException(401,'Invalid individual transfer signature')
        if self.plan and time.time()>self.plan['expires_at']:
            raise HTTPException(403,'Individual transfer permit expired')
        return pin,digest

    async def body(self,request,limit,digest):
        declared=request.headers.get('content-length','')
        if not declared.isdigit() or int(declared)>limit:
            raise HTTPException(413,'Individual transfer size limit')
        raw=bytearray()
        async for chunk in request.stream():
            raw.extend(chunk)
            if len(raw)>limit:raise HTTPException(413,'Individual transfer size limit')
        if len(raw)!=int(declared) or hashlib.sha256(raw).hexdigest()!=digest:
            raise HTTPException(422,'Individual transfer byte integrity mismatch')
        return bytes(raw)

    async def manifest(self,request):
        pin,digest=self.authorize(request)
        if digest!=pin:raise HTTPException(403,'Manifest is outside the configured permit')
        raw=await self.body(request,2_000_000,digest)
        try:
            plan=json.loads(raw);model=plan['model']
            if (plan['schema_version']!=1 or model not in ('mimmi','yui')
                    or type(plan['expires_at']) is not int
                    or not time.time()<plan['expires_at']<=time.time()+86400
                    or not 1<=len(plan['albums'])<=30):raise ValueError()
            previous=await self.catalog(model)
            known={a['id'] for a in previous['albums']}
            objects={};count=0;total=0;album_ids=set()
            for album in plan['albums']:
                aid=album['id']
                if not ALBUM.fullmatch(aid) or aid not in known or aid in album_ids:raise ValueError()
                album_ids.add(aid)
                for p in album['images']:
                    count+=1
                    if (p.get('higher_resolution_replacement') or p.get('work_identity_saved_cut_anchors',0)<3
                            or type(p['source_photo_number']) is not int or p['source_photo_number']<1):raise ValueError()
                    for preview in (False,True):
                        h=p['preview_sha256' if preview else 'sha256']
                        size=p['preview_bytes' if preview else 'bytes']
                        ext='webp' if preview else p['extension']
                        w=p['preview_width' if preview else 'width'];height=p['preview_height' if preview else 'height']
                        if (not SHA.fullmatch(h) or type(size) is not int or not 100<=size<=24_000_000
                                or ext not in ('jpg','jpeg','png','webp') or type(w) is not int
                                or type(height) is not int or min(w,height)<100 or w*height>40_000_000):raise ValueError()
                        target=('previews' if preview else 'originals')+'/'+aid+'/'+h+'.'+ext
                        fmt={'jpg':'JPEG','jpeg':'JPEG','png':'PNG','webp':'WEBP'}[ext]
                        obj=objects.setdefault(h,{'bytes':size,'width':w,'height':height,'format':fmt,'targets':[]})
                        if (obj['bytes'],obj['width'],obj['height'],obj['format'])!=(size,w,height,fmt):raise ValueError()
                        if target not in obj['targets']:obj['targets'].append(target);total+=size
            if not 1<=count<=1200 or total>512_000_000:raise ValueError()
        except HTTPException:raise
        except Exception:raise HTTPException(422,'Invalid bounded individual-photo manifest')
        if self.plan is None:
            self.plan=plan;self.objects=objects;self.root.mkdir(parents=True,exist_ok=True)
        return {'accepted':True,'photos':count,'objects':len(objects),'bytes':total,
                'remote_verified_objects':len(self.verified),'remote_verified_sha256':sorted(self.verified),
                'catalog_published':False}

    async def file(self,request,digest):
        _,body_digest=self.authorize(request)
        if not self.plan or digest not in self.objects or digest!=body_digest:
            raise HTTPException(403,'Photo is outside the configured manifest')
        spec=self.objects[digest]
        raw=await self.body(request,spec['bytes'],digest)
        try:
            with Image.open(BytesIO(raw)) as im:im.verify()
            with Image.open(BytesIO(raw)) as im:
                im.load()
                if im.size!=(spec['width'],spec['height']) or im.format!=spec['format']:raise ValueError()
        except Exception:raise HTTPException(422,'Transferred photo did not decode as declared')
        async with self.locks.setdefault(digest,asyncio.Lock()):
            if digest not in self.verified:
                async with self.workers:
                    local=self.root/digest
                    local.write_bytes(raw)
                    try:
                        for target in spec['targets']:
                            await self.put(self.plan['model'],local,target,False)
                            # One fresh remote read after a classified network
                            # interruption. Never retry a write, access denial,
                            # or byte/hash mismatch as a successful photo.
                            try:
                                back=await self.read(self.plan['model'],target,spec['bytes']+1)
                            except HTTPException as error:
                                if error.status_code!=502 or (error.headers or {}).get('X-Archive-Read-Cause')!='transport_interruption':raise
                                await asyncio.sleep(1)
                                back=await self.read(self.plan['model'],target,spec['bytes']+1)
                            if len(back)!=spec['bytes'] or hashlib.sha256(back).hexdigest()!=digest:
                                raise HTTPException(502,'Remote individual photo SHA mismatch')
                        self.verified.add(digest)
                    finally:local.unlink(missing_ok=True)
        return {'remote_sha256_verified':True,'objects':len(spec['targets']),
                'verified':len(self.verified),'total':len(self.objects),'catalog_published':False}

    async def finish(self,request,album_id=None):
        pin,digest=self.authorize(request)
        await self.body(request,0,digest)
        selected=[a for a in self.plan['albums'] if album_id is None or a['id']==album_id] if self.plan else []
        required={p[field] for a in selected for p in a['images'] for field in ('sha256','preview_sha256')}
        if not selected or not required.issubset(self.verified):
            raise HTTPException(409,'Some individual objects are not remotely verified')
        # Only an existing, concurrency-locked Actions import can merge/publish
        # the live catalogue. This endpoint writes a separate private queue.
        albums=[]
        for album in selected:
            images=[]
            for i,p in enumerate(album['images'],1):
                row={k:p[k] for k in ('sha256','bytes','width','height','preview_sha256','preview_bytes',
                    'source_photo_number','work_identity_saved_cut_anchors')}
                row.update(number=i,key='originals/'+album['id']+'/'+p['sha256']+'.'+p['extension'],
                    preview='previews/'+album['id']+'/'+p['preview_sha256']+'.webp',
                    source_numbering='public_web_filename_not_publisher_original')
                images.append(row)
            albums.append({'id':album['id'],'title':album.get('title',album['id']),'images':images,
                           'source_coverage':album.get('source_coverage',{})})
        batch=pin if album_id is None else hashlib.sha256((pin+'\n'+album_id).encode()).hexdigest()
        document={'schema_version':1,'model':self.plan['model'],'source_batch_sha256':batch,
                  'parent_manifest_sha256':pin,'remote_verified_objects':sum(len(self.objects[h]['targets']) for h in required),'albums':albums}
        raw=(json.dumps(document,ensure_ascii=False,sort_keys=True,separators=(',',':'))+'\n').encode()
        path=self.root/(batch+'.json');path.write_bytes(raw)
        target='metadata/pending-individual/'+self.plan['model']+'/'+batch+'.json'
        try:
            await self.put(self.plan['model'],path,target,False)
            if await self.read(self.plan['model'],target,len(raw)+1)!=raw:
                raise HTTPException(502,'Private transfer queue readback mismatch')
        finally:path.unlink(missing_ok=True)
        return {'pending_batch':batch,'remote_verified_photos':sum(len(a['images']) for a in albums),
                'catalog_published':False,'gallery_qa_passed':False}

    async def connection_state(self,request):
        _,digest=self.authorize(request)
        await self.body(request,0,digest)
        if not self.plan or not self.state_provider:raise HTTPException(404,'Owner connection state is unavailable')
        # This callback verifies both existing archive folders and returns
        # ciphertext bound to the existing server key, never a raw credential.
        return {'sealed_state':await self.state_provider()}


def install(app,catalog,put,read,state_provider=None):
    transfer=IndividualImport(catalog,put,read,state_provider=state_provider)
    @app.post('/internal/individual-import/manifest')
    async def manifest(request:Request):return await transfer.manifest(request)
    @app.put('/internal/individual-import/file/{digest}')
    async def file(digest:str,request:Request):return await transfer.file(request,digest)
    @app.post('/internal/individual-import/finish')
    async def finish(request:Request):return await transfer.finish(request)
    @app.post('/internal/individual-import/finish/{album_id}')
    async def finish_album(album_id:str,request:Request):return await transfer.finish(request,album_id)
    @app.post('/internal/individual-import/connection-state')
    async def connection_state(request:Request):return await transfer.connection_state(request)
    return transfer
