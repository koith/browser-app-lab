"""Real signatures, immutable bytes and private queue publication guards."""
import base64
import copy
import hashlib
from io import BytesIO
import json
import os
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import patch

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import Encoding,PublicFormat
from fastapi import FastAPI,HTTPException
from fastapi.testclient import TestClient
from PIL import Image
from gateway.individual_import import IndividualImport,install
from gateway.sealed_session import seal,restore


class TransferTests(unittest.TestCase):
    def setUp(self):
        self.directory=tempfile.TemporaryDirectory();self.remote={};self.writes=[];self.corrupt=False
        self.private=Ed25519PrivateKey.generate()
        fixture=Image.new('RGB',(400,600));fixture.putdata([
            (x*7%256,y*11%256,(x+y)*17%256) for y in range(600) for x in range(400)])
        self.photo=BytesIO();fixture.save(self.photo,format='JPEG')
        self.preview=BytesIO();fixture.resize((200,300)).save(self.preview,format='WEBP',lossless=True)
        self.raw=self.photo.getvalue();self.thumb=self.preview.getvalue()
        sha=lambda b:hashlib.sha256(b).hexdigest()
        self.plan={'schema_version':1,'model':'mimmi','expires_at':int(time.time())+3600,
          'albums':[{'id':'saved-work','images':[{'sha256':sha(self.raw),'bytes':len(self.raw),
             'width':400,'height':600,'extension':'jpg','preview_sha256':sha(self.thumb),
             'preview_bytes':len(self.thumb),'preview_width':200,'preview_height':300,
             'source_photo_number':15,'work_identity_saved_cut_anchors':3}]}]}
        self.manifest=json.dumps(self.plan,sort_keys=True).encode();self.pin=sha(self.manifest)
        self.config=patch.dict(os.environ,{'ARCHIVE_IMPORT_MANIFEST_SHA256':self.pin,
            'ARCHIVE_IMPORT_PUBLIC_KEY':base64.b64encode(self.private.public_key().public_bytes(Encoding.Raw,PublicFormat.Raw)).decode()})
        self.config.start()
        async def catalog(model):return {'albums':[{'id':'saved-work','images':[]}]}
        async def put(model,path,key,overwrite):
            self.assertFalse(overwrite);data=Path(path).read_bytes()
            if key in self.remote:self.assertEqual(self.remote[key],data,'Existing bytes must never be replaced')
            self.remote[key]=data;self.writes.append(key)
        async def read(model,key,limit):return b'bad' if self.corrupt else self.remote[key]
        app=FastAPI();self.worker=install(app,catalog,put,read);self.worker.root=Path(self.directory.name)
        self.client=TestClient(app)

    def tearDown(self):self.client.close();self.config.stop();self.directory.cleanup()

    def call(self,method,path,data=b'',stamp=None,key=None):
        stamp=str(int(time.time()) if stamp is None else stamp);digest=hashlib.sha256(data).hexdigest()
        message='\n'.join((method,path,self.pin,stamp,digest)).encode()
        signature=(key or self.private).sign(message)
        return self.client.request(method,path,content=data,headers={'x-archive-time':stamp,
            'x-archive-body-sha256':digest,'x-archive-signature':base64.b64encode(signature).decode(),
            'content-length':str(len(data))})

    def test_exact_original_remote_readback_then_separate_private_queue(self):
        self.assertEqual(self.call('POST','/internal/individual-import/manifest',self.manifest).status_code,200)
        incomplete=self.call('POST','/internal/individual-import/finish');self.assertEqual(incomplete.status_code,409)
        for data in [self.raw,self.thumb]:
            h=hashlib.sha256(data).hexdigest();reply=self.call('PUT','/internal/individual-import/file/'+h,data)
            self.assertEqual(reply.status_code,200,reply.text);self.assertTrue(reply.json()['remote_sha256_verified'])
        reply=self.call('POST','/internal/individual-import/finish');self.assertEqual(reply.status_code,200,reply.text)
        self.assertFalse(reply.json()['catalog_published']);self.assertFalse(reply.json()['gallery_qa_passed'])
        self.assertFalse(any(p=='metadata/catalog.json' for p in self.writes))
        self.assertIn(self.raw,self.remote.values());self.assertIn(self.thumb,self.remote.values())
        queued=json.loads(self.remote['metadata/pending-individual/mimmi/'+self.pin+'.json'])
        self.assertEqual(queued['albums'][0]['images'][0]['source_photo_number'],15)

    def test_bad_signature_expiry_and_unlisted_image_are_rejected_before_write(self):
        path='/internal/individual-import/manifest'
        self.assertEqual(self.call('POST',path,self.manifest,key=Ed25519PrivateKey.generate()).status_code,401)
        self.assertEqual(self.call('POST',path,self.manifest,stamp=int(time.time())-600).status_code,401)
        self.assertEqual(self.call('POST',path,self.manifest+b' ').status_code,403)
        self.assertEqual(self.call('POST',path,self.manifest).status_code,200)
        unlisted=b'unlisted object';h=hashlib.sha256(unlisted).hexdigest()
        self.assertEqual(self.call('PUT','/internal/individual-import/file/'+h,unlisted).status_code,403)
        self.worker.plan['expires_at']=int(time.time())-1
        self.assertEqual(self.call('POST','/internal/individual-import/finish').status_code,403)
        self.assertFalse(self.writes)

    def test_corrupt_remote_bytes_never_produce_ready_queue(self):
        self.assertEqual(self.call('POST','/internal/individual-import/manifest',self.manifest).status_code,200)
        self.corrupt=True;h=hashlib.sha256(self.raw).hexdigest()
        self.assertEqual(self.call('PUT','/internal/individual-import/file/'+h,self.raw).status_code,502)
        self.assertEqual(self.call('POST','/internal/individual-import/finish').status_code,409)
        self.assertFalse(any(p.startswith('metadata/') for p in self.writes))

    def test_resume_acknowledges_only_fully_verified_objects_and_complete_work(self):
        path='/internal/individual-import/manifest'
        self.assertEqual(self.call('POST',path,self.manifest).json()['remote_verified_sha256'],[])
        h=hashlib.sha256(self.raw).hexdigest()
        self.call('PUT','/internal/individual-import/file/'+h,self.raw)
        self.assertEqual(self.call('POST',path,self.manifest).json()['remote_verified_sha256'],[h])
        self.assertEqual(self.call('POST','/internal/individual-import/finish/saved-work').status_code,409)
        ph=hashlib.sha256(self.thumb).hexdigest();self.call('PUT','/internal/individual-import/file/'+ph,self.thumb)
        result=self.call('POST','/internal/individual-import/finish/saved-work')
        self.assertEqual(result.status_code,200,result.text)
        self.assertEqual(result.json()['remote_verified_photos'],1)
        self.assertFalse(result.json()['catalog_published'])
        self.assertEqual(self.call('POST','/internal/individual-import/finish/unlisted-work').status_code,409)
        self.assertNotIn('metadata/catalog.json',self.writes)

    def test_only_classified_transport_read_is_retried_once_without_duplicate_write(self):
        self.call('POST','/internal/individual-import/manifest',self.manifest)
        calls=[]
        async def read(model,key,limit):
            calls.append(key)
            if len(calls)==1:raise HTTPException(502,'Cloud unavailable',headers={'X-Archive-Read-Cause':'transport_interruption'})
            return self.remote[key]
        self.worker.read=read;h=hashlib.sha256(self.raw).hexdigest()
        response=self.call('PUT','/internal/individual-import/file/'+h,self.raw)
        self.assertEqual(response.status_code,200,response.text)
        self.assertEqual(len(calls),2);self.assertEqual(len(self.writes),1)
        async def denied(model,key,limit):raise HTTPException(451,'restricted')
        self.worker.read=denied;ph=hashlib.sha256(self.thumb).hexdigest()
        self.assertEqual(self.call('PUT','/internal/individual-import/file/'+ph,self.thumb).status_code,451)
        self.assertNotIn(ph,self.worker.verified)

    def test_completed_work_queue_never_admits_the_unfinished_other_work(self):
        second=copy.deepcopy(self.plan['albums'][0]);second['id']='other-saved-work'
        second['images'][0].update(sha256='c'*64,preview_sha256='d'*64)
        self.plan['albums'].append(second)
        self.manifest=json.dumps(self.plan,sort_keys=True).encode();self.pin=hashlib.sha256(self.manifest).hexdigest()
        os.environ['ARCHIVE_IMPORT_MANIFEST_SHA256']=self.pin
        async def catalog(model):return {'albums':[{'id':'saved-work'},{'id':'other-saved-work'}]}
        self.worker.catalog=catalog
        self.assertEqual(self.call('POST','/internal/individual-import/manifest',self.manifest).status_code,200)
        for data in (self.raw,self.thumb):
            h=hashlib.sha256(data).hexdigest();self.assertEqual(self.call('PUT','/internal/individual-import/file/'+h,data).status_code,200)
        self.assertEqual(self.call('POST','/internal/individual-import/finish').status_code,409)
        reply=self.call('POST','/internal/individual-import/finish/saved-work')
        self.assertEqual(reply.status_code,200,reply.text)
        queue=json.loads(self.remote['metadata/pending-individual/mimmi/'+reply.json()['pending_batch']+'.json'])
        self.assertEqual([a['id'] for a in queue['albums']],['saved-work'])
        self.assertEqual(queue['remote_verified_objects'],2)

    def test_encrypted_restart_state_requires_exact_active_operator_permit(self):
        called=[];cookie='ndus=offline-owner-cookie';owner_key='offline-existing-private-server-key'
        async def state():called.append(1);return seal(cookie,owner_key)
        self.worker.state_provider=state
        path='/internal/individual-import/connection-state'
        self.assertEqual(self.client.post(path,content=b'').status_code,401);self.assertFalse(called)
        self.assertEqual(self.call('POST','/internal/individual-import/manifest',self.manifest).status_code,200)
        response=self.call('POST',path)
        self.assertEqual(response.status_code,200);self.assertNotIn(cookie,response.text)
        self.assertEqual(restore(response.json()['sealed_state'],owner_key),cookie)
        self.worker.plan['expires_at']=int(time.time())-1
        self.assertEqual(self.call('POST',path).status_code,403);self.assertEqual(len(called),1)


if __name__=='__main__':unittest.main(verbosity=2)
