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

if __name__=='__main__':unittest.main(verbosity=2)
