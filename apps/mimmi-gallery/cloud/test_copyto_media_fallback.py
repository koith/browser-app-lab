"""Simulate provider JSON on cat, same-account copyto JPEG, and SHA refusal."""
import asyncio
import hashlib
import os
import sys
import unittest
from unittest.mock import patch
from pathlib import Path
os.environ.setdefault('GALLERY_ACCESS_TOKEN','local-test-token')
os.environ.setdefault('RCLONE_CONFIG_ARCHIVE_COOKIE','local-test-cookie')
from gateway import main as gateway

class Stream:
    def __init__(self,raw):self.raw=raw
    async def read(self,n=65536):
        raw,self.raw=self.raw[:n],self.raw[n:]
        return raw

class Proc:
    def __init__(self,raw=b''):
        self.stdout=Stream(raw)
        self.stderr=Stream(b'')
        self.returncode=0
    async def wait(self):return 0
    async def communicate(self):return b'',b''
    def kill(self):self.returncode=-9

class GatewayCopytoTests(unittest.IsolatedAsyncioTestCase):
    async def test_real_bytes_recovered_but_only_exact_digest_accepted(self):
        original=b'JPEG-size-simulated-file-with-exact-hash'*20
        async def factory(*args,**kwargs):
            if args[1]=='cat':
                return Proc(b'{"errno":400141}')
            if args[1]=='copyto':
                Path(args[3]).write_bytes(original)
                return Proc()
            raise AssertionError('Unexpected operation')
        with patch.object(gateway.asyncio,'create_subprocess_exec',factory):
            with patch.object(gateway,'cookie_header',lambda value:value):
                got=await gateway.rclone_bytes('originals/fixture/a.jpg',len(original)+1)
                self.assertEqual(got,original)
                gateway._media_cache.clear()
                actual=await gateway.verified_remote_media('originals/fixture/a.jpg',len(original),
                    hashlib.sha256(original).hexdigest(),'archive:MimmiArchive')
                self.assertEqual(actual,original)
                gateway._media_cache.clear()
                with self.assertRaises(Exception):
                    await gateway.verified_remote_media('originals/fixture/a.jpg',len(original),
                        hashlib.sha256(b'different').hexdigest(),'archive:MimmiArchive')

    async def test_pending_mimmi_metadata_recovers_from_same_owner_copyto(self):
        # A successful rclone cat may contain provider JSON errno=400141,
        # not the SHA-pinned original queue. The same-owner normal file read
        # must remain possible; endpoint schema checks happen separately.
        batch='d'*64
        path='metadata/pending-individual/mimmi/'+batch+'.json'
        original=b'{"model":"mimmi","schema_version":1,"source_batch_sha256":"'+batch.encode()+b'"}'
        calls=[]
        async def factory(*args,**kwargs):
            calls.append(args[1])
            if args[1]=='cat':
                return Proc(b'{"errno":400141}')
            if args[1]=='copyto':
                self.assertEqual(args[2],'archive:MimmiArchive/'+path)
                Path(args[3]).write_bytes(original)
                return Proc()
            raise AssertionError('Unexpected operation')
        with patch.object(gateway.asyncio,'create_subprocess_exec',factory),\\
             patch.object(gateway,'cookie_header',lambda value:value):
            recovered=await gateway.rclone_bytes(path,2_000_001,remote='archive:MimmiArchive')
        self.assertEqual(recovered,original)
        self.assertEqual(calls,['cat','copyto'])

    async def test_pending_metadata_fallback_denies_wrong_owner_or_freeform_path(self):
        batch='e'*64
        for path in ('metadata/pending-individual/yui/'+batch+'.json',
                     'metadata/pending-individual/mimmi/../catalog.json',
                     'metadata/catalog.json'):
            self.assertFalse(gateway.same_owner_copyto_read_allowed(
                path,2_000_001,'archive:MimmiArchive'))
        self.assertTrue(gateway.same_owner_copyto_read_allowed(
            'metadata/pending-individual/mimmi/'+batch+'.json',
            2_000_001,'archive:MimmiArchive'))
        self.assertFalse(gateway.same_owner_copyto_read_allowed(
            'metadata/pending-individual/mimmi/'+batch+'.json',
            6_000_000,'archive:MimmiArchive'))


if __name__=='__main__':unittest.main(verbosity=2)
