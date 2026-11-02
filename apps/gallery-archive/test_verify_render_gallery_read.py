#!/usr/bin/env python3
"""Regression tests for read-only gateway retry and strict payload verification."""
import io
import json
import unittest
import urllib.error
from verify_render_gallery_read import (
    ORIGIN, MAX_CATALOG, read_gateway, verify_catalog, verify_cover
)


class Fake:
    status=200
    def __init__(self,body,headers=None):
        self.body=body
        self.headers=headers or {}
    def __enter__(self):return self
    def __exit__(self,*args):return False
    def read(self,length):return self.body[:length]


def http_error(code):
    return urllib.error.HTTPError(ORIGIN+'/api/catalog',code,"simulated",{},io.BytesIO())


class GatewayReadTests(unittest.TestCase):
    def test_retry_only_two_transient_502_reads_then_exact_catalog(self):
        calls=[];pauses=[]
        good=Fake(json.dumps({'model':'mimmi','albums':[{'images':[{}]*3}]}).encode())
        def opener(url,timeout):
            calls.append((url,timeout))
            if len(calls)<3:raise http_error(502)
            return good
        body,headers=read_gateway('/api/catalog',1000,opener=opener,
                                  pause=pauses.append)
        self.assertEqual(body,good.body)
        self.assertEqual(len(calls),3)
        self.assertEqual(pauses,[1,2])
        self.assertTrue(all(c==(ORIGIN+'/api/catalog',35) for c in calls))
        _,count=verify_catalog('mimmi',body,3)
        self.assertEqual(count,3)

    def test_refuse_403_and_challenge_without_fallback(self):
        calls=[]
        def opener(url,timeout):
            calls.append(url)
            raise http_error(403)
        with self.assertRaisesRegex(RuntimeError,"403"):
            read_gateway('/api/catalog',1000,opener=opener,pause=lambda _:None)
        self.assertEqual(len(calls),1)
        with self.assertRaisesRegex(ValueError,"model/schema mismatch"):
            verify_catalog('mimmi',b'{"errno":400141}',1)

    def test_three_failed_502_reads_end_as_failure(self):
        calls=[]
        def opener(url,timeout):
            calls.append(url);raise http_error(502)
        with self.assertRaisesRegex(RuntimeError,"502"):
            read_gateway('/api/catalog',1000,opener=opener,pause=lambda _:None)
        self.assertEqual(len(calls),3)

    def test_only_allowed_read_paths_and_no_unbounded_responses(self):
        for path in ('/internal/terabox-session-refresh','/api/media/x/1/original',
                     '/api/cover/mimmi/../../secret?v='+'a'*24,
                     '/api/cover/yui/good/5?v=notsha',
                     'https://other.invalid/api/catalog'):
            with self.subTest(path=path),self.assertRaises(ValueError):
                read_gateway(path,1000,opener=lambda *_a,**_k:Fake(b''))
        with self.assertRaisesRegex(ValueError,"bound"):
            read_gateway('/api/catalog',MAX_CATALOG+1)
        with self.assertRaisesRegex(ValueError,"bound"):
            read_gateway('/api/catalog',1000,attempts=10)

    def test_cover_rejects_success_shaped_json_or_wrong_mime(self):
        image=b'RIFF'+b'0'*4+b'WEBP'+b'Q'*300
        headers={'Content-Type':'image/webp','Cache-Control':'private, max-age=604800'}
        self.assertEqual(verify_cover(image,headers),len(image))
        for bad,h in [(b'{"errno":0}'*30,headers),
                      (image,{'Content-Type':'application/json','Cache-Control':headers['Cache-Control']}),
                      (image,{'Content-Type':'image/webp','Cache-Control':'no-store'})]:
            with self.assertRaisesRegex(ValueError,'invalid'):verify_cover(bad,h)

    def test_oversize_and_wrong_model_cannot_be_accepted(self):
        def opener(url,timeout):return Fake(b'a'*1001)
        with self.assertRaisesRegex(ValueError,"bound"):
            read_gateway('/api/catalog',1000,opener=opener,pause=lambda _:None)
        with self.assertRaisesRegex(ValueError,"model/schema mismatch"):
            verify_catalog('mimmi',b'{"model":"yui","albums":[]}',0)


if __name__ == '__main__':
    unittest.main(verbosity=2)
