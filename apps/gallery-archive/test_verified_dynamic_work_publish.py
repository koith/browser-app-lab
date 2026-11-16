#!/usr/bin/env python3
"""New verified edition must really publish, not vanish behind old registry.

A source-name match without independent source-page verification must never
authorize a new work; an exact independently checked public work must survive
image decoding, SHA, the Pages stored manifest and a second idempotent replay.
"""
import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from PIL import Image
from publish_new_public_photos_to_pages import publish


MODEL='mimmi'
NEW_ID='djawa-mimmi-new-edition'
SOURCE='https://public-new-editions.org/mimmi/djawa-new-edition'


class NewPublishedWorkTests(unittest.TestCase):
    def make_fixture(self,root,proof):
        base=root/'apps/mimmi-gallery'
        base.mkdir(parents=True)
        (base/'owner-index.json').write_text(json.dumps({
            'schema_version':1,'model':MODEL,'albums':[{
                'id':'existing-old-work','images':[{'sha256':'a'*64}]}]}))
        (base/'stored-albums.json').write_text(json.dumps({'albums':[]}))
        (base/'public-work-pages.json').write_text(json.dumps({
            'albums':[{'id':'existing-old-work','title':'Existing',
                        'source':'https://public-old-editions.org/work'}]}))
        stage=root/'stage'
        path=stage/'originals'/NEW_ID/'one.jpg'
        path.parent.mkdir(parents=True)
        Image.new('RGB',(420,630),(20,70,120)).save(path,format='JPEG')
        raw=path.read_bytes()
        sha=hashlib.sha256(raw).hexdigest()
        catalog={
            'schema_version':1,'model':MODEL,
            'albums':[{'id':NEW_ID,'title':'DJAWA Mimmi New Edition',
                'images':[{'number':1,'key':str(path.relative_to(stage)),
                           'sha256':sha,'bytes':len(raw),'width':420,'height':630,
                           'source_url':'https://cdn.public-new-editions.org/new_01.jpg'}]}],
            'verified_new_work_sources':proof}
        (stage/'metadata').mkdir()
        (stage/'metadata/catalog.json').write_text(json.dumps(catalog))
        return base,stage,raw,sha

    @staticmethod
    def proof():
        return [{
            'id':NEW_ID,'title':'DJAWA Mimmi New Edition',
            'source':SOURCE,
            'verified_same_work_pages':[SOURCE],
            'proof':'unique_named_work_page_model_and_edition'}]

    def test_unregistered_but_exact_verified_photos_reach_real_gallery(self):
        with tempfile.TemporaryDirectory() as tmp:
            base,stage,raw,digest=self.make_fixture(Path(tmp),self.proof())
            first=publish(MODEL,stage,root=Path(tmp))
            self.assertEqual(first['new_sha_verified_originals'],1,first)
            self.assertEqual(first['new_verified_source_work_ids'],[NEW_ID])
            manifest=json.loads((base/'stored-albums.json').read_text())
            self.assertEqual([a['id'] for a in manifest['albums']],[NEW_ID])
            album=manifest['albums'][0]
            self.assertEqual(album['source'],SOURCE)
            photo=album['images'][0]
            self.assertEqual(photo['sha256'],digest)
            self.assertEqual((base/photo['url']).read_bytes(),raw)
            # Idempotent readback on main: subsequent replay must NOT add
            # a duplicate SHA or create a second album.
            second=publish(MODEL,stage,root=Path(tmp))
            self.assertEqual(second['new_sha_verified_originals'],0)
            manifest2=json.loads((base/'stored-albums.json').read_text())
            self.assertEqual(len(manifest2['albums']),1)
            self.assertEqual(len(manifest2['albums'][0]['images']),1)

    def test_existing_owner_edition_absent_from_public_work_list_publishes(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            evidence=self.proof()
            evidence[0]['proof']='owner_catalog_work_with_reviewed_public_source'
            base,stage,raw,digest=self.make_fixture(root,evidence)
            owner_path=base/'owner-index.json'
            owner=json.loads(owner_path.read_text())
            owner['albums'].append({'id':NEW_ID,'title':'DJAWA Mimmi New Edition',
                                   'images':[{'sha256':'b'*64,'number':1}]})
            owner_path.write_text(json.dumps(owner))
            result=publish(MODEL,stage,root=root)
            self.assertEqual(result['new_sha_verified_originals'],1,result)
            photo=json.loads((base/'stored-albums.json').read_text())['albums'][0]['images'][0]
            self.assertEqual((base/photo['url']).read_bytes(),raw)
            self.assertEqual(photo['sha256'],digest)

    def test_existing_owner_claim_requires_matching_actual_owner_title(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            evidence=self.proof()
            evidence[0]['proof']='owner_catalog_work_with_reviewed_public_source'
            base,stage,_,_=self.make_fixture(root,evidence)
            owner_path=base/'owner-index.json'
            owner=json.loads(owner_path.read_text())
            owner['albums'].append({'id':NEW_ID,'title':'Another Edition',
                                   'images':[{'sha256':'b'*64,'number':1}]})
            owner_path.write_text(json.dumps(owner))
            with self.assertRaisesRegex(ValueError,'UNVERIFIED_NEW_WORK_PUBLICATION_SOURCE'):
                publish(MODEL,stage,root=root)

    def test_unknown_work_without_independent_proof_is_not_published(self):
        with tempfile.TemporaryDirectory() as tmp:
            base,stage,_,_=self.make_fixture(Path(tmp),[])
            result=publish(MODEL,stage,root=Path(tmp))
            self.assertEqual(result['new_sha_verified_originals'],0)
            self.assertEqual(json.loads((base/'stored-albums.json').read_text())['albums'],[])

    def test_snippet_or_cross_model_or_private_url_fails_closed(self):
        for variant in ('snippet','foreign','private','mismatch'):
            with self.subTest(variant=variant),tempfile.TemporaryDirectory() as tmp:
                proof=self.proof()
                if variant=='snippet':
                    proof[0]['proof']='search_snippet_only'
                elif variant=='foreign':
                    proof[0]['id']='yui-unrelated-work'
                elif variant=='private':
                    proof[0]['source']='https://127.0.0.1/metadata'
                    proof[0]['verified_same_work_pages']=[proof[0]['source']]
                else:
                    proof[0]['source']='https://public-new-editions.org/unverified'
                _,stage,_,_=self.make_fixture(Path(tmp),proof)
                if variant=='foreign':
                    # Even a properly formed proof for a different work
                    # cannot create photos for this unrelated album.
                    proof[0]['title']='Other Valid Work'
                    (stage/'metadata/catalog.json').write_text(json.dumps({
                        **json.loads((stage/'metadata/catalog.json').read_text()),
                        'verified_new_work_sources':proof}))
                    result=publish(MODEL,stage,root=Path(tmp))
                    self.assertEqual(result['new_sha_verified_originals'],0)
                else:
                    with self.assertRaisesRegex(ValueError,
                                                'UNVERIFIED_NEW_WORK_PUBLICATION_SOURCE'):
                        publish(MODEL,stage,root=Path(tmp))


if __name__=='__main__':
    unittest.main()
