#!/usr/bin/env python3
"""Exact-byte original publisher sample backfill and source rights regressions."""
import hashlib
import json
import tempfile
import unittest
from io import BytesIO
from pathlib import Path

from PIL import Image
from official_sample_recovery import (
    missing_verified_publisher_samples, matching_recorded_variant)
from direct_photo_pipeline import collect, reviewed_direct_source, reviewed_direct_media


def photo(seed):
    image=Image.new('RGB',(400,600))
    image.putdata([((x*7+seed)%256,(y*11+seed)%256,((x+y)*13+seed)%256)
                   for y in range(600) for x in range(400)])
    output=BytesIO()
    image.save(output,format='JPEG',quality=93)
    return output.getvalue()


def record(raw,url):
    return {'url':url,'sha256':hashlib.sha256(raw).hexdigest(),
            'bytes':len(raw),'width':400,'height':600}


def fixtures(root):
    base=root/'apps/mimmi-gallery'
    base.mkdir(parents=True)
    (base/'stored-albums.json').write_text('{"albums":[]}')
    source='https://djawaphoto.com/portfolio/mimmi-real-sample/'
    candidate='https://djawaphoto.com/wp-content/uploads/2026/09/fresh.jpg'
    duplicate='https://djawaphoto.com/wp-content/uploads/2026/09/already.jpg'
    original=photo(5)
    new=photo(81)
    old=photo(80)
    later=photo(99)
    document={'model':{'id':'mimmi'},'albums':[{
        'id':'djawa-test-work','title':'Mimmi real sample','publisher':'DJAWA',
        'source':source,
        'samples':[record(old,candidate),record(new,candidate),
                   record(original,duplicate),record(later,duplicate)]}]}
    (base/'official-previews.json').write_text(json.dumps(document))
    (base/'public-work-pages.json').write_text(json.dumps({'albums':[{
        'id':'rehosted-work','source':'https://www.v2ph.com/album/a123.html',
        'title':'Mimmi rehosted'}]}))
    owner={'model':'mimmi','schema_version':1,'albums':[
        {'id':'djawa-test-work','images':[{
            'number':1,'sha256':hashlib.sha256(original).hexdigest()}]},
        {'id':'rehosted-work','images':[]}]}
    return base,source,candidate,duplicate,owner,new,old,original


class Tests(unittest.TestCase):
    def test_same_url_with_two_versions_is_one_candidate(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);base,source,url,duplicate,owner,new,old,original=fixtures(root)
            gap=missing_verified_publisher_samples(base,owner,'mimmi')
            self.assertEqual(len(gap['djawa-test-work']),1)
            self.assertEqual(gap['djawa-test-work'][0]['url'],url)
            self.assertEqual(len(gap['djawa-test-work'][0]['recorded_variants']),2)
            self.assertNotIn(duplicate,[x['url'] for x in gap['djawa-test-work']])
            self.assertEqual(missing_verified_publisher_samples(base,owner,'yui'),{})
            self.assertTrue(matching_recorded_variant(new,record(new,url),gap['djawa-test-work'][0]['recorded_variants']))
            self.assertFalse(matching_recorded_variant(photo(56),record(new,url),gap['djawa-test-work'][0]['recorded_variants']))

    def test_stages_only_verified_unsaved_publisher_url_and_preserves_number(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);base,source,url,duplicate,owner,new,old,original=fixtures(root)
            class Client:
                blocked_origins=set()
                def __init__(self):self.calls=[]
                def get(self,request):
                    self.calls.append(request)
                    if request==url:return type('R',(),{'content':new})()
                    if request==source:
                        return type('R',(),{'content':b'<h1>Mimmi real sample</h1><article>Album</article>'})()
                    raise AssertionError('Unaudited or duplicate source requested: '+request)
            client=Client()
            report=collect(root,'mimmi',owner,root/'stage',5,3,client,
                           reviewed_source_only=True)
            self.assertEqual(report['new_local_individual_files'],1,report)
            self.assertNotIn(duplicate,client.calls)
            self.assertEqual(report['owner_census_source_coverage']['reviewed_storage_scope_works'],1)
            rows=json.loads((root/'stage/metadata/catalog.json').read_text())['albums'][0]['images']
            self.assertEqual(len(rows),1)
            self.assertEqual(rows[0]['number'],2)
            self.assertEqual(rows[0]['sha256'],hashlib.sha256(new).hexdigest())
            self.assertEqual((root/'stage'/rows[0]['key']).read_bytes(),new)
            journal=(root/'stage/journal.jsonl').read_text().splitlines()
            self.assertEqual(len(journal),1)
            self.assertEqual(json.loads(journal[0])['photo']['number'],2)
            self.assertEqual(report['results'][0]['verified_official_unique_urls_staged'],1)
            self.assertEqual(client.calls[0],url,'Previously verified missing official photo goes first')

    def test_pages_local_sha_is_not_private_terabox_proof(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)
            base,source,url,duplicate,owner,new,old,original=fixtures(root)
            # The gallery already renders the file from Pages, but its SHA
            # does NOT occur in the TeraBox owner ledger.
            public={'albums':[{'id':'djawa-test-work','images':[{
                'number':1,'url':'stored-albums/djawa-test-work/0001.jpeg',
                'sha256':hashlib.sha256(new).hexdigest(),
                'bytes':len(new),'width':400,'height':600}]}]}
            (base/'stored-albums.json').write_text(json.dumps(public))
            class Client:
                blocked_origins=set()
                def get(self,target):
                    if target==url:return type('R',(),{'content':new})()
                    if target==source:
                        return type('R',(),{'content':b'<h1>Mimmi real sample</h1><article>Album</article>'})()
                    raise AssertionError('Unexpected source')
            report=collect(root,'mimmi',owner,root/'stage',5,2,Client(),
                           reviewed_source_only=True)
            self.assertEqual(report['new_local_individual_files'],1,report)
            self.assertEqual(report['results'][0]['verified_official_unique_urls_staged'],1)
            staged=json.loads((root/'stage/metadata/catalog.json').read_text())
            self.assertEqual(staged['albums'][0]['images'][0]['number'],2)
            self.assertEqual(staged['albums'][0]['images'][0]['sha256'],
                             hashlib.sha256(new).hexdigest())
            # An already private exact original never enters the backfill.
            already_private={'model':'mimmi','schema_version':1,
                'albums':[{'id':'djawa-test-work','images':[
                    {'number':1,'sha256':hashlib.sha256(original).hexdigest()},
                    {'number':2,'sha256':hashlib.sha256(new).hexdigest()}]}]}
            again=collect(root,'mimmi',already_private,root/'second-stage',5,2,
                          Client(),reviewed_source_only=True)
            self.assertEqual(again['new_local_individual_files'],0)

    def test_rights_reviewed_mode_rejects_rehost_and_unrelated_media(self):
        self.assertTrue(reviewed_direct_source(
            'https://djawaphoto.com/portfolio/nikke-alice/','mimmi'))
        self.assertTrue(reviewed_direct_media(
            'https://djawaphoto.com/wp-content/uploads/2026/09/sample.jpg',
            'https://djawaphoto.com/portfolio/nikke-alice/','mimmi'))
        self.assertFalse(reviewed_direct_media(
            'https://imgx001.pixibb.com/a.jpg',
            'https://djawaphoto.com/portfolio/nikke-alice/','mimmi'))
        for page in ('https://www.v2ph.com/album/a123.html',
                     'https://cosplay.pixibb.com/djawa-mimmi/',
                     'https://www.junmeitu.com/mimmi/album'):
            self.assertFalse(reviewed_direct_source(page,'mimmi'))
        self.assertTrue(reviewed_direct_source(
            'https://x.com/super_yuisan/status/1234567890123','yui'))
        self.assertTrue(reviewed_direct_source(
            'https://teapawt.net/super_yuisan','yui'))
        self.assertTrue(reviewed_direct_source(
            'https://teapawt.net/Mimmi_official','mimmi'))
        self.assertFalse(reviewed_direct_source(
            'https://teapawt.net/Mimmi_official','yui'))
        self.assertFalse(reviewed_direct_source(
            'https://x.com/anyoneelse/status/1234567890123','yui'))
        self.assertFalse(reviewed_direct_source(
            'https://x.com/super_yuisan/status/1234567890123','mimmi'))

    def test_never_accept_unrecorded_changed_publisher_bytes(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);base,source,url,duplicate,owner,new,old,original=fixtures(root)
            class Client:
                blocked_origins=set()
                def get(self,target):
                    if target==url:return type('R',(),{'content':photo(123)})()
                    if target==source:return type('R',(),{'content':b'<h1>Mimmi real sample</h1>'})()
                    raise AssertionError('Unexpected host or image')
            report=collect(root,'mimmi',owner,root/'stage',5,2,Client(),
                           reviewed_source_only=True)
            self.assertEqual(report['new_local_individual_files'],0)
            self.assertEqual(report['results'][0]['failure_categories'].get(
                'official_publisher_bytes_not_same_sha_as_verified_history'),1)


if __name__=='__main__':
    unittest.main(verbosity=2)
