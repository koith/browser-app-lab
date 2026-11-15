"""Offline exact-work source discovery must become real, safe image-byte staging."""
from io import BytesIO
import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from PIL import Image

from direct_photo_pipeline import collect, safe_registered_public_page
from verified_source_bridge import eligible_source_pages, article_scoped_images
from public_work_photo_extractor import ordinary_public_https_image
from direct_photo_pipeline import _work_token_matched_in_heading

MODEL='mimmi'
ALBUM='djawa-pop-kitty-party'
OFFICIAL='https://djawaphoto.com/portfolio/pop-kitty-party/'
SOURCE='https://www.cosplay-public-gallery.net/mimmi-pop-kitty-party'
ASSET='https://cdn.cosplay-public-gallery.net/photos/mimmi-pop-kitty-party-001.jpg'
UNRELATED='https://cdn.cosplay-public-gallery.net/ads/other-model-001.jpg'


def evidence():
    return {'schema_version':1,'model':MODEL,
            'targets':[{'id':ALBUM,'title':'Pop Kitty Party','urls':[SOURCE]}],
            'search_results':[{'id':ALBUM,'urls':[SOURCE],
                'observations':[{'model':MODEL,'album_id':ALBUM,
                    'source':SOURCE,'name':'Mimmi Pop Kitty Party',
                    'proof':'unique_named_work_page_model_and_edition'}]}]}


def html(model='Mimmi', work='Pop Kitty Party'):
    return (f'<html><head><title>{model} {work}</title></head><body>'
            f'<article><h1>{model} {work}</h1><img src="{ASSET}"></article>'
            f'<aside class="advert"><img src="{UNRELATED}"></aside></body></html>').encode()


class VerifiedDiscoveryBridgeTests(unittest.TestCase):
    def test_verified_source_can_enter_storage_scope(self):
        a=eligible_source_pages(evidence(),MODEL,safe_registered_public_page)
        self.assertEqual(a,{ALBUM:{SOURCE}})
        allowed=article_scoped_images(html(),SOURCE,MODEL,ALBUM,
            'Pop Kitty Party',_work_token_matched_in_heading,
            ordinary_public_https_image)
        self.assertEqual(allowed,{ASSET})

    def test_unverified_alias_or_other_model_rejected(self):
        document=evidence()
        document['search_results'][0]['observations'][0]['proof']='search_snippet_only'
        self.assertFalse(eligible_source_pages(document,MODEL,safe_registered_public_page))
        document=evidence()
        self.assertFalse(eligible_source_pages(document,'yui',safe_registered_public_page))
        self.assertFalse(article_scoped_images(html(work='Another Edition'),SOURCE,MODEL,
             ALBUM,'Pop Kitty Party',_work_token_matched_in_heading,
             ordinary_public_https_image))

    def test_end_to_end_fresh_same_work_media_without_host_allowlist(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            base=root/'apps/mimmi-gallery'
            base.mkdir(parents=True)
            (base/'stored-albums.json').write_text(json.dumps({'model':MODEL,'albums':[]}))
            (base/'public-work-pages.json').write_text(json.dumps({'albums':[{
                'id':ALBUM,'title':'Pop Kitty Party',
                'source':OFFICIAL,'source_pages':[]}]}))
            owner={'schema_version':1,'model':MODEL,'albums':[
                {'id':ALBUM,'title':'Pop Kitty Party','images':[
                    {'number':1,'sha256':'1'*64,'bytes':5000}]}]}
            with BytesIO() as b:
                Image.new('RGB',(450,640),(12,130,200)).save(b,'JPEG',quality=91)
                raw=b.getvalue()
            source=root/'verified.json'
            source.write_text(json.dumps(evidence()))
            class Session:
                blocked_origins=set()
                def get(self,url):
                    if url==OFFICIAL:
                        return type('Result',(),{'content':b'<h1>Mimmi Pop Kitty Party</h1><article></article>'})()
                    if url==SOURCE:
                        return type('Result',(),{'content':html()})()
                    if url==ASSET:
                        return type('Result',(),{'content':raw})()
                    raise AssertionError('unrelated or unverified media must not be fetched '+url)
            report=collect(root,MODEL,owner,root/'stage',
                           max_new=2,max_pages=3,client=Session(),
                           reviewed_source_only=True,reverse_evidence=source,
                           alternative_engines=False,render_budget=0)
            self.assertEqual(report['new_local_individual_files'],1,report)
            doc=json.loads((root/'stage/metadata/catalog.json').read_text())
            row=doc['albums'][0]['images'][0]
            self.assertEqual(row['sha256'],hashlib.sha256(raw).hexdigest())
            self.assertEqual((root/'stage'/row['key']).read_bytes(),raw)
            self.assertEqual(report['owner_census_source_coverage']['reverse_source_pages_admitted'],1)

    def test_no_unreviewed_result_is_automatically_scraped(self):
        doc=evidence()
        doc['search_results']=[]
        self.assertEqual(eligible_source_pages(doc,MODEL,safe_registered_public_page),{})


if __name__=='__main__':
    unittest.main()
