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

    def test_article_og_title_must_be_checked_by_downstream_edition_gate(self):
        # When the search bridge accepts a page using real on-page OG title
        # metadata, the collector must recognize that SAME edition as well.
        good=(b'<html><head><meta property="og:title" '
              b'content="DJAWA Mimmi Pop Kitty Party"></head><body>'
              b'<article><img src="https://public-gallery.org/picture.jpg">'
              b'</article></body></html>')
        bad=good.replace(b'Pop Kitty Party',b'Nikke Alice')
        self.assertTrue(_work_token_matched_in_heading(
            good,'Pop Kitty Party',ALBUM,MODEL))
        self.assertFalse(_work_token_matched_in_heading(
            bad,'Pop Kitty Party',ALBUM,MODEL))

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
                # The decoder deliberately rejects flat placeholders. Simulate
                # an actual detailed photo instead of a single-color test tile.
                im=Image.new('RGB',(450,640))
                im.putdata([((x*7+y*5)%256,(x*3+y*11)%256,
                             (x*13+y*17)%256)
                            for y in range(640) for x in range(450)])
                im.save(b,'JPEG',quality=91)
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

    def test_reverse_results_cover_new_named_works_even_outside_original_eight(self):
        from source_alias_search import (
            hydrate_all_registered_works, merge_image_reverse_sites,
            exact_work_in_text)
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary)
            base=root/'apps/mimmi-gallery'
            base.mkdir(parents=True)
            (base/'public-work-pages.json').write_text(json.dumps({'albums':[
                {'id':'mimmi-white','title':'Mimmi — White',
                 'source':'https://djawaphoto.com/portfolio/mimmi-white/'},
                {'id':'mimmi-summer','title':'Mimmi — Summer',
                 'source':'https://djawaphoto.com/portfolio/mimmi-summer/'}]}))
            db={'works':{},'model_names':{'mimmi':[{'name':'Mimmi'}],
                                          'yui':[{'name':'Yui Sim'}]}}
            self.assertEqual(hydrate_all_registered_works(db,'mimmi',root),2)
            self.assertTrue(exact_work_in_text('mimmi:mimmi-white','DJAWA Mimmi White'))
            self.assertFalse(exact_work_in_text('mimmi:mimmi-white','DJAWA Mimmi Summer'))
            url='https://www.cosplay-public-gallery.net/djawa-mimmi-white'
            evidence={'model':'mimmi','research_only':True,'results':[{
                'model':'mimmi','album_id':'mimmi-white','candidate_pages':[{'url':url}]
            }]}
            html_page='<title>DJAWA Mimmi White</title><h1>Mimmi White</h1><article>Official work</article>'
            class Session:
                def get(self,requested,**kwargs):
                    if requested!=url:raise AssertionError(requested)
                    return type('R',(),{'status_code':200,
                        'headers':{'Content-Type':'text/html'},
                        'content':html_page.encode(),'text':html_page})()
            output=[]
            added=merge_image_reverse_sites(db,evidence,'mimmi',output,Session(),limit=16)
            self.assertEqual(len(added),1)
            self.assertEqual(output[0]['id'],'mimmi-white')
            self.assertEqual(output[0]['urls'],[url])
            self.assertEqual(output[0]['observations'][0]['proof'],
                             'unique_named_work_page_model_and_edition')

    def test_unknown_reverse_seed_maps_to_exact_registered_owner_work(self):
        from source_alias_search import hydrate_all_registered_works, merge_image_reverse_sites
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            base=root/'apps/mimmi-gallery'
            base.mkdir(parents=True)
            # Owner catalog is larger than the approved-source registry.
            (base/'public-work-pages.json').write_text(json.dumps({
                'albums':[{'id':'mimmi-white','title':'Mimmi — White',
                    'source':'https://djawaphoto.com/portfolio/mimmi-white/'}]}))
            (base/'owner-index.json').write_text(json.dumps({
                'model':'mimmi','albums':[{'id':'mimmi-teddy-bear',
                'title':'DJAWA Mimmi Teddy Bear',
                'images':[{'number':1,'sha256':'a'*64,'bytes':50000}]}]}))
            db={'works':{},'model_names':{'mimmi':[{'name':'Mimmi'}],
                                         'yui':[{'name':'Yui'}]}}
            count=hydrate_all_registered_works(db,'mimmi',root)
            self.assertEqual(count,2)
            self.assertIn('mimmi:mimmi-teddy-bear',db['works'])
            # Genuine Yandex CBIR identified the host page + source image
            # but the result card only has a numeric URL and generic title.
            url='https://new-public-gallery.org/collection/184994'
            report={'research_only':True,'results':[{'model':'mimmi',
                # This legacy/unclassified SHA photo is NOT the registered work.
                'album_id':'legacy-unknown-source','candidate_pages':[
                    {'url':url,'label':'Shared image from public collection',
                     'source_engine':'yandex_sites',
                     'matched_image_url':'https://cdn.public-gallery.org/photobook-01.jpg'},
                    {'url':'https://new-public-gallery.org/other-model',
                     'label':'Unrelated other model'}]}]}
            html_page='<title>DJAWA Mimmi Teddy Bear</title><h1>Mimmi Teddy Bear</h1><article>Mimmi new public images</article>'
            class Session:
                def get(self,requested,**kwargs):
                    self_url=url
                    if requested!=self_url:raise AssertionError(requested)
                    return type('R',(),{'status_code':200,
                        'headers':{'Content-Type':'text/html'},
                        'content':html_page.encode(),'text':html_page})()
            results=[]
            statistics={}
            matched=merge_image_reverse_sites(db,report,'mimmi',results,Session(),
                                              limit=10,stats_out=statistics)
            self.assertEqual(len(matched),1,matched)
            self.assertEqual(statistics['cross_album_seed_recovered'],1,statistics)
            self.assertEqual(statistics['structured_visual_host_page_without_edition_hint'],1,statistics)
            self.assertEqual(statistics['no_exact_edition_hint'],1,statistics)
            self.assertEqual(statistics['accepted_verified_same_work_pages'],1,statistics)
            self.assertEqual(matched[0]['album_id'],'mimmi-teddy-bear')
            self.assertEqual(matched[0]['reverse_seed_album_id'],'legacy-unknown-source')
            self.assertEqual(results[0]['observations'][0]['proof'],
                             'unique_named_work_page_model_and_edition')
            assert eligible_source_pages({'schema_version':1,'model':'mimmi',
                'search_results':results},'mimmi',safe_registered_public_page)=={
                'mimmi-teddy-bear':{url}}

    def test_no_unreviewed_result_is_automatically_scraped(self):
        doc=evidence()
        doc['search_results']=[]
        self.assertEqual(eligible_source_pages(doc,MODEL,safe_registered_public_page),{})


if __name__=='__main__':
    unittest.main()
