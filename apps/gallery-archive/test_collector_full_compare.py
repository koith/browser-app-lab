#!/usr/bin/env python3
"""Offline safety and exhaustivity tests for the all-work benchmark."""
from io import BytesIO
from pathlib import Path
import tempfile

from PIL import Image,ImageDraw
import collector_full_compare as full
from collector_full_census import census,select,ROOT


def test():
    d=census(ROOT)
    assert len(d['targets'])==d['summary']['total_targets']
    assert any(t['kind']=='work' and t.get('owner_registered') for t in d['targets'])
    no_source={'kind':'visual_lead','model':'yui','id':'missing','title':'Missing','urls':[]}
    r=full.inspect_work(no_source,None,None)
    assert r['reason']=='title_only_search_needed'
    assert r['new_private_originals_stored']==r['new_gallery_photos_verified']==0
    base='https://djawaphoto.com/portfolio/example/'
    html=b'''<html><head><title>Mimmi</title></head><body class="sidebar-right">
       <article><div class="portfolio-content"><p>Mimmi photos</p>
       <img src="https://djawaphoto.com/wp-content/uploads/2026/09/sample-1.jpg">
       <a rel="next" href="?page=2">Next</a>
       <div class="related"><img src="https://djawaphoto.com/wp-content/uploads/2026/09/other.jpg"></div>
       </div></article></body></html>'''
    assert full.pagination_from_html(html,base,base)==[base+'?page=2']
    assert full.independent_scrapy_extract(html,base,'mimmi')[1]=='independent_scrapy_selector'
    # A newly discovered public CDN must NOT be rejected merely because the
    # old in-house engine did not whitelist that host.
    independent='https://new-public-cdn.photos-example.org/work/001.jpg'
    from collector_engines_ab import safe_photo as legacy_safe_photo
    assert full.alternative_safe_photo(independent)
    assert not legacy_safe_photo(independent)
    assert not full.alternative_safe_photo('https://127.0.0.1/private.jpg')
    assert not full.alternative_safe_photo('http://new-public-cdn.photos-example.org/work/001.jpg')
    independent_html=('<html><title>Mimmi public photo</title><article>Mimmi <img src="'+independent+'"></article></html>').encode()
    extracted,_=full.independent_scrapy_extract(independent_html,base,'mimmi')
    assert independent in extracted,extracted
    im=Image.new('RGB',(400,600),'white')
    ImageDraw.Draw(im).rectangle((40,50,300,500),fill=(12,30,200))
    dst=BytesIO();im.save(dst,format='JPEG')
    pic=dst.getvalue()
    class R:
        status_code=200
        def __init__(self,raw):self.content=raw
        def raise_for_status(self):pass
    class S:
        def get(self,url,**kwargs):
            if url.endswith('jpg'):return R(pic)
            if 'page=2' in url:return R(html.replace(b'<a rel="next" href="?page=2">Next</a>',b''))
            return R(html)
    class Client:
        def __init__(self):self.session=S()
        def get(self,url):return self.session.get(url)
    class Browser:
        def extract(self,url,model):
            return ['https://djawaphoto.com/wp-content/uploads/2026/09/sample-1.jpg'],'ok'
    old=full.gallery_dl_work
    full.gallery_dl_work=lambda url:([],'unsupported_extractor')
    try:
        work={'kind':'work','id':'test-full','model':'mimmi',
              'title':'Mimmi photos','urls':[base],'direct_image_urls':[],
              'owner_registered':True,'owner_slots':0,'owner_distinct_sha':0}
        got=full.inspect_work(work,Client(),Browser(),max_pages=4,max_images=4)
        assert got['registered_page_attempts']==2,got
        assert got['actual_public_images_decoded']==1,got
        assert got['new_private_originals_stored']==0,got
        assert got['extra_decoded_sha_not_in_baseline']==0,got
        assert got['engine_page_statuses'].get('scrapy:independent_scrapy_selector')==2,got
        assert 'scrapy:NameError' not in got['engine_page_statuses'],got
        # If an image is already registered in a historical manifest, an
        # alternative extractor rediscovering it is NOT a new photo.
        known={**work,'direct_image_urls':[
            'https://djawaphoto.com/wp-content/uploads/2026/09/sample-1.jpg']}
        known_result=full.inspect_work(known,Client(),Browser(),max_pages=4,max_images=4)
        assert known_result['extra_asset_groups_candidate_not_proven_distinct_cuts']==0,known_result
        assert known_result['extra_decoded_sha_not_in_baseline']==0,known_result
        class FakePage:
            def goto(self,*args,**kwargs):
                class Response:status=200
                return Response()
            def evaluate(self,*args):pass
            def wait_for_timeout(self,*args):pass
            def content(self):return html.decode()
        real_chromium_parser=full.LiveBrowser()
        real_chromium_parser.page=FakePage()
        browser_urls,browser_status=real_chromium_parser.extract(base,'mimmi')
        assert browser_status=='independent_scrapy_selector',(browser_status,browser_urls)
        assert 'https://djawaphoto.com/wp-content/uploads/2026/09/sample-1.jpg' in browser_urls
        capped=full.inspect_work(work,Client(),Browser(),max_pages=1,max_images=1)
        assert 'max_pages_per_target' in capped['limits'],capped
    finally:full.gallery_dl_work=old
    print('FULL_COLLECTOR_COMPARE_OFFLINE_PASS')


if __name__=='__main__':test()
