import hashlib
import importlib.util
from io import BytesIO
import json
from pathlib import Path
import tempfile
import unittest
from PIL import Image
from direct_photo_pipeline import collect, inspect, page_images, same_variant, public_full_variant, rotated_registered_page_queue, verified_alternative_candidates, merge_owner_census_sources, _work_token_matched_in_heading, safe_page


def photo(seed):
    im=Image.new('RGB',(400,600))
    im.putdata([((x*7+seed)%256,(y*11+seed)%256,((x+y)*13+seed)%256) for y in range(600) for x in range(400)])
    buf=BytesIO();im.save(buf,format='JPEG',quality=93);return buf.getvalue()


class DirectTests(unittest.TestCase):
    def test_photographer_original_source_is_scoped_to_exact_yui_post(self):
        from direct_photo_pipeline import (
            YUI_PHOTOGRAPHER_ORIGINAL_X, YUI_PHOTOGRAPHER_PUBLIC_VIEW,
            YUI_PHOTOGRAPHER_ORIGINAL_MEDIA, reviewed_direct_source,
            reviewed_direct_media, safe_registered_public_page)
        self.assertEqual(len(YUI_PHOTOGRAPHER_ORIGINAL_MEDIA),4)
        for source in (YUI_PHOTOGRAPHER_ORIGINAL_X,YUI_PHOTOGRAPHER_PUBLIC_VIEW):
            self.assertTrue(safe_registered_public_page(source,'yui'))
            self.assertTrue(reviewed_direct_source(source,'yui'))
            self.assertFalse(reviewed_direct_source(source,'mimmi'))
            for asset in YUI_PHOTOGRAPHER_ORIGINAL_MEDIA:
                self.assertTrue(reviewed_direct_media(asset,source,'yui'))
            self.assertFalse(reviewed_direct_media(
                'https://pbs.twimg.com/media/UNRELATED.jpg?name=orig',source,'yui'))
        self.assertFalse(safe_registered_public_page(
            'https://teapawt.net/chinokun_photo/media','yui'))
        source=YUI_PHOTOGRAPHER_PUBLIC_VIEW
        links=''.join('<a href="'+url+'">photo</a>' for url in sorted(
            YUI_PHOTOGRAPHER_ORIGINAL_MEDIA))
        html=('<title>치노쿤 @chinokun_photo</title>'
              '<article><p>2026 10 10 심유이 @super_yuisan</p>'
              +links+'<a href="https://pbs.twimg.com/media/UNRELATED.jpg?name=orig">other</a>'
              +'</article>')
        urls,more,state=page_images(html.encode(),source,'yui')
        self.assertEqual(set(urls),YUI_PHOTOGRAPHER_ORIGINAL_MEDIA)
        self.assertEqual(more,[])
        self.assertEqual(state,'scoped_public_page')
        urls,more,state=page_images(
            html.replace('심유이','다른 모델').encode(),source,'yui')
        self.assertEqual(urls,[])
        self.assertEqual(state,'photographer_or_model_identity_unverified')

    def test_photographer_page_produces_actual_staged_image_pair_without_fake_count(self):
        from direct_photo_pipeline import (YUI_PHOTOGRAPHER_ORIGINAL_X,
            YUI_PHOTOGRAPHER_PUBLIC_VIEW,YUI_PHOTOGRAPHER_ORIGINAL_MEDIA)
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);base=root/'apps/yui-gallery'
            base.mkdir(parents=True)
            (base/'stored-albums.json').write_text(
                '{"model":"yui","albums":[]}')
            (base/'public-work-pages.json').write_text(json.dumps(
                {'model':'yui','albums':[{'id':'yui-chinokun-illustar-2026-public',
                  'title':'Yui photographer original public',
                  'priority':0,'source':YUI_PHOTOGRAPHER_ORIGINAL_X,
                  'source_pages':[YUI_PHOTOGRAPHER_PUBLIC_VIEW]}]}))
            prior=photo(4);new=photo(99)
            old={'model':'yui','schema_version':1,'albums':[{
                'id':'existing','title':'Existing','images':[{
                    'number':1,'sha256':hashlib.sha256(prior).hexdigest()}]}]}
            media=sorted(YUI_PHOTOGRAPHER_ORIGINAL_MEDIA)
            html=('<title>치노쿤 @chinokun_photo</title>'
                  '<article>2026 10 10 심유이 @super_yuisan'
                  +''.join('<a href="'+v+'">Photo</a>' for v in media)
                  +'</article>').encode()
            class Client:
                blocked_origins=set()
                def get(self,url):
                    if url==YUI_PHOTOGRAPHER_ORIGINAL_X:
                        raise ValueError('Ordinary X public page unavailable')
                    if url==YUI_PHOTOGRAPHER_PUBLIC_VIEW:
                        return type('Response',(),{'content':html})()
                    if url in media:
                        return type('Response',(),{'content':new})()
                    raise ValueError('Unregistered URL')
            report=collect(root,'yui',old,root/'stage',
                           max_new=2,max_pages=2,client=Client(),
                           reviewed_source_only=True,alternative_engines=False)
            self.assertEqual(report['new_local_individual_files'],1,report)
            staged=json.loads((root/'stage/metadata/catalog.json').read_text())
            self.assertEqual(staged['albums'][0]['id'],
                             'yui-chinokun-illustar-2026-public')
            row=staged['albums'][0]['images'][0]
            self.assertEqual((root/'stage'/row['key']).read_bytes(),new)
            self.assertEqual(len((root/'stage'/row['preview']).read_bytes()),
                             row['preview_bytes'])


    def test_blocked_source_does_not_consume_page_budget_for_other_registered_host(self):
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);base=root/'apps/mimmi-gallery';base.mkdir(parents=True)
            (base/'stored-albums.json').write_text('{"model":"mimmi","albums":[]}')
            source='https://www.junmeitu.com/mimmi/christmas/'
            other='https://djawaphoto.com/portfolio/mimmi-christmas/'
            image='https://djawaphoto.com/wp-content/uploads/2026/02/new-cut.jpg'
            (base/'public-work-pages.json').write_text(json.dumps({'albums':[{
                'id':'mimmi-xmas','title':'Mimmi Christmas','source':source,
                'source_pages':[source+'?page=2',source+'?page=3',other]}]}))
            prior=photo(1);cut=photo(31)
            owner={'model':'mimmi','schema_version':1,'albums':[{
                'id':'mimmi-xmas','images':[{'number':1,'sha256':
                            hashlib.sha256(prior).hexdigest()}]}]}
            class Client:
                blocked_origins={'https://www.junmeitu.com'}
                def get(self,url):
                    if url==other:
                        return type('R',(),{'content':
                            f'<h1>Mimmi Christmas</h1><article><img src="{image}"></article>'.encode()})()
                    if url==image:return type('R',(),{'content':cut})()
                    raise AssertionError('Blocked origin must not be visited')
            with patch('direct_photo_pipeline.page_images',
                       return_value=([image],[],'scoped_public_page')):
                report=collect(root,'mimmi',owner,root/'stage',
                               2,1,Client(),alternative_engines=False)
            self.assertEqual(report['new_local_individual_files'],1,report)
            self.assertEqual(report['results'][0]['blocked_origin_pages_not_retried'],3)
            self.assertEqual(report['results'][0]['pages'],1)

    @unittest.skipUnless(importlib.util.find_spec('scrapy') is not None,
                         'Real selector engine required')
    def test_reverse_image_source_lead_can_become_decoded_individual_photo(self):
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);(root/'apps/yui-gallery').mkdir(parents=True)
            (root/'apps/gallery-archive').mkdir(parents=True)
            (root/'apps/gallery-archive/global_source_registry.json').write_text('{"sources":[]}')
            (root/'apps/yui-gallery/stored-albums.json').write_text('{"model":"yui","albums":[]}')
            lead=root/'reverse.json'
            page='https://public-gallery.example.org/summer/source-page'
            asset='https://images.public-gallery.example.org/summer/17.jpg'
            lead.write_text(json.dumps({'model':'yui','targets':[{
                'id':'missing-summer','title':'Yui Sim Summer',
                'urls':[page],'owner_registered':False}]}))
            before=photo(10);new=photo(99)
            owner={'model':'yui','schema_version':1,'albums':[{
              'id':'older-gallery','images':[{'number':1,
              'sha256':hashlib.sha256(before).hexdigest()}]}]}
            class Client:
                def get(self,url):
                    if url==page:return type('R',(),{'content':
                        f'<h1>Yui Sim Summer</h1><article><img src="{asset}"></article>'.encode()})()
                    if url==asset:return type('R',(),{'content':new})()
                    raise ValueError('unexpected')
            with patch('collector_full_census.census',return_value={'targets':[]}),patch(
                    'direct_photo_pipeline.page_images',return_value=([],[],'no_public_photos')):
                report=collect(root,'yui',owner,root/'stage',2,3,Client(),
                    alternative_engines=True,render_budget=0,reverse_evidence=lead)
            self.assertEqual(report['new_local_individual_files'],1,report)
            self.assertEqual(report['owner_census_source_coverage']['reverse_source_pages_admitted'],1)
            rows=json.loads((root/'stage/metadata/catalog.json').read_text())['albums']
            self.assertEqual(rows[0]['id'],'missing-summer')
            self.assertEqual((root/'stage'/rows[0]['images'][0]['key']).read_bytes(),new)

    @unittest.skipUnless(importlib.util.find_spec('scrapy') is not None,
                         'Actual Scrapy dependency required')
    def test_unowned_named_work_becomes_staged_album_only_after_identity_evidence(self):
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);base=root/'apps/yui-gallery';base.mkdir(parents=True)
            (base/'stored-albums.json').write_text('{"model":"yui","albums":[]}')
            (root/'apps/gallery-archive').mkdir()
            (root/'apps/gallery-archive/global_source_registry.json').write_text('{"sources":[]}')
            page='https://public-gallery.example.org/yui-sim-spring/'
            img='https://images.public-gallery.example.org/spring/08.jpg'
            existing=photo(7);new=photo(77)
            owner={'model':'yui','schema_version':1,'albums':[{
                'id':'older-work','title':'Older Yui Work','images':[{
                    'number':1,'sha256':hashlib.sha256(existing).hexdigest()}]}]}
            census={'targets':[{'kind':'work','model':'yui','id':'new-yui-spring',
                  'title':'Yui Sim Spring','owner_registered':False,
                  'manifest_sources':['public-work-pages.json'],'urls':[page]}]}
            class Client:
                def get(self,url):
                    if url==page:
                        return type('R',(),{'content':f'<h1>Yui Sim Spring</h1><article><img src="{img}"></article>'.encode()})()
                    if url==img:return type('R',(),{'content':new})()
                    raise ValueError('unexpected source')
            with patch('collector_full_census.census',return_value=census),patch(
                 'direct_photo_pipeline.page_images',
                 return_value=([],[],'no_public_photos')):
                got=collect(root,'yui',owner,root/'stage',5,4,Client(),
                            alternative_engines=True,render_budget=0)
            self.assertEqual(got['new_local_individual_files'],1,got)
            self.assertEqual(got['owner_census_source_coverage']['newly_scheduled_unowned_works'],1)
            catalog=json.loads((root/'stage/metadata/catalog.json').read_text())
            self.assertEqual(catalog['albums'][0]['id'],'new-yui-spring')
            p=catalog['albums'][0]['images'][0]
            self.assertEqual((root/'stage'/p['key']).read_bytes(),new)

    def test_all_recorded_public_hosts_without_static_allowlist(self):
        from direct_photo_pipeline import safe_registered_public_page
        self.assertTrue(safe_registered_public_page(
            'https://public-gallery.example.org/album/sim-yui-spring','yui'))
        self.assertTrue(safe_registered_public_page(
            'https://x.com/super_yuisan/status/1234567890123456789','yui'))
        self.assertFalse(safe_registered_public_page(
            'https://x.com/unrelated_status/status/1234567890123456789','yui'))
        self.assertFalse(safe_registered_public_page(
            'https://x.com/super_yuisan/status/1234567890123456789','mimmi'))
        self.assertFalse(safe_registered_public_page(
            'https://x.com/super_yuisan','yui'))
        self.assertFalse(safe_registered_public_page(
            'https://127.0.0.1/photo/album','yui'))

    def test_only_exact_creators_public_status_media(self):
        url='https://x.com/super_yuisan/status/1234567890123456789'
        good='https://pbs.twimg.com/media/AAA123.jpg?name=large'
        wrong='https://pbs.twimg.com/media/WRONG123.jpg'
        raw=f'''<html><article><a href="/super_yuisan">super_yuisan</a>
             <img src="{good}"></article>
             <article><a href="/different_artist">someone</a>
             <img src="{wrong}"></article></html>'''
        urls,_,status=page_images(raw,url,'yui')
        self.assertEqual(status,'scoped_public_page')
        self.assertEqual(urls,[good])
        self.assertEqual(page_images(raw,url,'mimmi')[0],[])

    @unittest.skipUnless(importlib.util.find_spec('scrapy') is not None,
                         'Real Scrapy required for second chance article extraction')
    def test_unlisted_registered_site_stages_real_photo(self):
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);base=root/'apps/yui-gallery';base.mkdir(parents=True)
            (base/'stored-albums.json').write_text('{"model":"yui","albums":[]}')
            page='https://public-gallery.example.org/yui-sim-spring/'
            photo_url='https://cdn.public-gallery.example.org/image?id=123'
            (base/'public-work-pages.json').write_text(json.dumps({'albums':[
                {'id':'yui-spring','source':page,'title':'Yui Sim Spring'}]}))
            prior=photo(3);fresh=photo(33)
            owner={'model':'yui','schema_version':1,'albums':[{'id':'yui-spring',
               'title':'Yui Sim Spring','images':[{'number':1,
               'sha256':hashlib.sha256(prior).hexdigest()}]}]}
            html=f'<h1>Yui Sim Spring</h1><article><img data-original="{photo_url}"></article>'
            class Client:
                def get(self,url):
                    if url==page:return type('R',(),{'content':html.encode()})()
                    if url==photo_url:return type('R',(),{'content':fresh})()
                    raise ValueError('unknown')
            with patch('direct_photo_pipeline.page_images',
                       return_value=([],[],'no_public_photos')):
                result=collect(root,'yui',owner,root/'stage',3,3,Client(),
                               alternative_engines=True,render_budget=0)
            self.assertEqual(result['new_local_individual_files'],1,result)
            self.assertEqual(result['alternative_staged_new_files'],1)
            item=json.loads((root/'stage/metadata/catalog.json').read_text())['albums'][0]['images'][0]
            self.assertEqual((root/'stage'/item['key']).read_bytes(),fresh)

    @unittest.skipUnless(importlib.util.find_spec('scrapy') is not None,
                         'Real Scrapy required for production additional extraction')
    def test_observed_cdn_without_extension_becomes_real_staged_image(self):
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            base=root/'apps/mimmi-gallery'
            base.mkdir(parents=True)
            (base/'stored-albums.json').write_text('{"model":"mimmi","albums":[]}')
            source='https://djawaphoto.com/portfolio/mimmi-new-gallery/'
            image='https://public-photo-cdn.example.com/image?photo=904'
            html=f'<h1>Mimmi New Gallery</h1><article class="post-content"><img data-original="{image}"></article>'
            (base/'official-previews.json').write_text(json.dumps({'albums':[
                {'id':'mimmi-extra','title':'Mimmi New Gallery','source':source}]}))
            original=photo(5)
            second=photo(50)
            owner={'model':'mimmi','schema_version':1,'albums':[{'id':'mimmi-extra',
              'images':[{'number':1,'sha256':hashlib.sha256(original).hexdigest()}]}]}
            class Client:
                def get(self,url):
                    if url==source:return type('R',(),{'content':html.encode()})()
                    if url==image:return type('R',(),{'content':second})()
                    raise ValueError('unregistered_url')
            with patch('direct_photo_pipeline.page_images',
                       return_value=([],[],'no_public_photos')):
                got=collect(root,'mimmi',owner,root/'stage',2,2,Client(),
                            alternative_engines=True,render_budget=0)
            self.assertEqual(got['new_local_individual_files'],1,got)
            self.assertEqual(got['alternative_staged_new_files'],1)
            catalog=json.loads((root/'stage/metadata/catalog.json').read_text())
            p=catalog['albums'][0]['images'][0]
            self.assertEqual((root/'stage'/p['key']).read_bytes(),second)
            self.assertEqual(p['measured_image_quality']['original_bytes'],len(second))
            self.assertEqual(p['measured_image_quality']['watermark_status'],'unverified')
            self.assertEqual(got['remote_verified_files'],0)

    def test_ambiguous_named_model_on_public_gallery_is_not_our_yui_sim(self):
        from direct_photo_pipeline import (
            PUBLIC_STRONG_MODEL, RESEARCH_WORK_HOSTS, _work_token_matched_in_heading,
            verified_alternative_candidates)
        page='https://www.junmeitu.com/beauty/yui-cream.html'
        self.assertIn('www.junmeitu.com',RESEARCH_WORK_HOSTS)
        known='https://i.wujituku.com/Yui-Cream-38.jpg'
        finder=lambda raw,url,model:([known],'independent_scrapy_selector')
        correct='<h1>Yui Sim Cream</h1><article>Yui Sim Cream</article>'
        different='<h1>Yui Nagase Cream</h1><article>Yui Nagase Cream</article>'
        self.assertTrue(_work_token_matched_in_heading(
            correct,'Yui Cream','cream228','yui'))
        self.assertFalse(PUBLIC_STRONG_MODEL['yui'].search('Yui Nagase Cream'))
        self.assertEqual(verified_alternative_candidates(
            correct,page,'yui',[],[],scrapy_extractor=finder)[0],[known])
        self.assertEqual(verified_alternative_candidates(
            different,page,'yui',[],[],scrapy_extractor=finder)[0],[])

    def test_registered_public_photo_hosts_are_crawled_but_social_login_and_offsite_media_are_not(self):
        for host in ('www.junmeitu.com','www.kaizty.com','misskon.com','www.imgcup.com'):
            self.assertTrue(safe_page('https://'+host+'/yui-cream/'),host)
        self.assertFalse(safe_page('https://x.com/super_yuisan'))
        self.assertFalse(safe_page('https://127.0.0.1/owner'))
        page='https://www.junmeitu.com/yui-cream/'
        image='https://www.junmeitu.com/photo/yui-cream-38.jpg'
        offsite='https://unexpected-media.example.com/yui-cream-38.jpg'
        html='<html><h1>Yui Sim Cream</h1><article>Yui Sim Cream</article></html>'
        urls,_=verified_alternative_candidates(html,page,'yui',[],[],
                    scrapy_extractor=lambda raw,url,model:([image,offsite],'real_scoped_selector'))
        self.assertEqual(urls,[image])

    def test_full_owner_source_census_restores_absent_album_jobs_without_cross_model_pollution(self):
        owner={'schema_version':1,'model':'yui','albums':[
            {'id':'ramen125','title':'Yui Ramen 125','images':[{'sha256':'a'*64}]},
            {'id':'held','title':'Yui Held','images':[]}]}
        book={'held':{'id':'held','source':'https://djawaphoto.com/portfolio/yui-held/',
                      'source_pages':[],'curated_images_only':True}}
        rows=[{'kind':'work','model':'yui','id':'ramen125',
               'urls':['https://djawaphoto.com/portfolio/yui-ramen/',
                       'https://djawaphoto.com/portfolio/yui-ramen/?page=2']},
              {'kind':'work','model':'yui','id':'held',
               'urls':['https://djawaphoto.com/portfolio/yui-held/?page=2']},
              {'kind':'work','model':'mimmi','id':'ramen125',
               'urls':['https://djawaphoto.com/portfolio/other-model/']},
              {'kind':'work','model':'yui','id':'not-in-owner',
               'urls':['https://djawaphoto.com/portfolio/not-owned/']}]
        counts=merge_owner_census_sources(book,owner,rows,'yui')
        self.assertEqual(counts['newly_scheduled_work_count'],1)
        self.assertEqual(counts['additional_registered_pages'],1)
        self.assertEqual(book['ramen125']['source_pages'],[
            'https://djawaphoto.com/portfolio/yui-ramen/?page=2'])
        self.assertEqual(len(book),2)
        self.assertTrue(book['ramen125']['curated_images_only'])
        self.assertTrue(_work_token_matched_in_heading(
            '<h1>Yui Ramen 125 new cut</h1>','Yui Ramen 125','ramen125','yui'))
        self.assertFalse(_work_token_matched_in_heading(
            '<h1>Yui Photo Gallery</h1>','Yui Ramen 125','ramen125','yui'))

    @unittest.skipUnless(importlib.util.find_spec('scrapy') is not None,
                         'Scrapy required for full owner work integration')
    def test_unindexed_owner_work_sourced_from_complete_census_can_stage_new_cut(self):
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);base=root/'apps/yui-gallery';base.mkdir(parents=True)
            (base/'stored-albums.json').write_text('{"model":"yui","albums":[]}')
            (root/'apps/gallery-archive').mkdir()
            (root/'apps/gallery-archive/global_source_registry.json').write_text('{"sources":[]}')
            page='https://djawaphoto.com/portfolio/yui-ramen/'
            image='https://djawaphoto.com/wp-content/uploads/2026/09/new-ramen-cut.jpg'
            html=f'<html><h1>Yui Ramen 125</h1><article>Yui Ramen <img src="{image}"></article></html>'
            saved=photo(15);new=photo(55)
            owner={'schema_version':1,'model':'yui','albums':[{'id':'ramen125',
                   'title':'Yui Ramen 125','images':[{'number':1,
                   'sha256':hashlib.sha256(saved).hexdigest()}]}]}
            census={'targets':[{'kind':'work','model':'yui','id':'ramen125',
                              'urls':[page],'direct_image_urls':[]}]}
            class Client:
                def get(self,url):
                    if url==page:return type('R',(),{'content':html.encode()})()
                    if url==image:return type('R',(),{'content':new})()
                    raise ValueError('unexpected URL '+url)
            with patch('collector_full_census.census',return_value=census),patch(
                 'direct_photo_pipeline.page_images',return_value=([],[],'no_public_photos')):
                report=collect(root,'yui',owner,root/'stage',5,3,
                               Client(),alternative_engines=True,render_budget=0)
            self.assertEqual(report['new_local_individual_files'],1,report)
            self.assertEqual(report['owner_census_source_coverage']['newly_scheduled_work_count'],1)
            self.assertEqual(report['alternative_staged_new_files'],1)
            self.assertEqual(report['remote_verified_files'],0)
            catalog=json.loads((root/'stage/metadata/catalog.json').read_text())
            self.assertEqual((root/'stage'/catalog['albums'][0]['images'][0]['key']).read_bytes(),new)

    @unittest.skipUnless(importlib.util.find_spec('scrapy') is not None,
                         'Real Scrapy test requires the Scrapy dependency')
    def test_registered_legacy_owner_source_can_store_a_distinct_verified_cut(self):
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);base=root/'apps/mimmi-gallery';base.mkdir(parents=True)
            (base/'stored-albums.json').write_text('{"model":"mimmi","albums":[]}')
            page='https://djawaphoto.com/portfolio/mimmi-editorial/'
            image='https://djawaphoto.com/wp-content/uploads/2026/09/legacy-extra-cut.jpg'
            (base/'official-previews.json').write_text(json.dumps({'albums':[{
                'id':'legacy-work','title':'Mimmi editorial','source_pages':[page]}]}))
            existing=photo(0);fresh=photo(80)
            owner={'schema_version':1,'model':'mimmi','albums':[{
                'id':'legacy-work','images':[{'number':1,
                    'sha256':hashlib.sha256(existing).hexdigest()}]}]}
            class Client:
                def __init__(self,heading):self.heading=heading
                def get(self,url):
                    html=f'<html><h1>{self.heading}</h1><article><img src="{image}"></article></html>'
                    return type('R',(),{'content':html.encode() if url==page else fresh})()
            with patch('direct_photo_pipeline.page_images',return_value=([],[],'no_public_photos')):
                allowed=collect(root,'mimmi',owner,root/'stage-good',3,3,
                    Client('Mimmi editorial'),alternative_engines=True,render_budget=0)
                denied=collect(root,'mimmi',owner,root/'stage-denied',3,3,
                    Client('Other model editorial'),alternative_engines=True,render_budget=0)
            self.assertEqual(allowed['new_local_individual_files'],1)
            self.assertEqual(allowed['alternative_staged_new_files'],1)
            self.assertEqual(denied['new_local_individual_files'],0)

    def test_scrapy_candidate_keeps_work_identity_and_rejects_existing_resizes(self):
        page='https://djawaphoto.com/portfolio/mimmi-book/'
        new='https://djawaphoto.com/wp-content/uploads/2026/09/new-cut.jpg'
        known='https://djawaphoto.com/wp-content/uploads/2026/09/old-cut.jpg'
        resized='https://djawaphoto.com/wp-content/uploads/2026/09/old-cut-480x640.jpg'
        html=f'<h1>Mimmi book</h1><article><img src="{new}"></article>'
        extractor=lambda raw,page,model:([resized,new,known,new],'independent_scrapy_selector')
        urls,status=verified_alternative_candidates(html,page,'mimmi',[],
                            [known],scrapy_extractor=extractor)
        self.assertEqual(urls,[new])
        self.assertEqual(status,'independent_scrapy_selector')
        other=html.replace('Mimmi book','Other person')
        self.assertEqual(verified_alternative_candidates(other,page,'mimmi',[],
                             [known],scrapy_extractor=extractor)[0],[])
        # No new photos from generic actor timelines without verified work scope.
        self.assertEqual(verified_alternative_candidates(
            '<h1>Mimmi</h1>', 'https://teapawt.net/Mimmi_official','mimmi',
            [],[],scrapy_extractor=extractor)[0],[])

    @unittest.skipUnless(importlib.util.find_spec('scrapy') is not None,
                         'Real Scrapy test requires the Scrapy dependency')
    def test_real_scrapy_discovered_image_enters_individual_storage_pipeline(self):
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);base=root/'apps/mimmi-gallery';base.mkdir(parents=True)
            (base/'stored-albums.json').write_text('{"model":"mimmi","albums":[]}')
            page='https://djawaphoto.com/portfolio/mimmi-book/'
            image='https://djawaphoto.com/wp-content/uploads/2026/09/additional-cut.jpg'
            (base/'official-previews.json').write_text(json.dumps(
                {'albums':[{'id':'mimmi-book','title':'Mimmi book','source':page}]}))
            previously=photo(1)
            incoming=photo(40)
            owner={'schema_version':1,'model':'mimmi','albums':[{
                'id':'mimmi-book','images':[{'number':1,
                'sha256':hashlib.sha256(previously).hexdigest()}]}]}
            html=f'<html><h1>Mimmi book</h1><article>Mimmi <img src="{image}"></article></html>'
            class Client:
                def get(self,url):
                    return type('Response',(),{'content':html.encode() if url==page else incoming})()
            # Reproduce a page type that the legacy scoped parser missed.
            with patch('direct_photo_pipeline.page_images',
                       return_value=([],[],'no_public_photos')):
                report=collect(root,'mimmi',owner,root/'stage',3,2,
                               Client(),alternative_engines=True,render_budget=0)
            self.assertEqual(report['new_local_individual_files'],1,report)
            row=report['results'][0]
            self.assertEqual(row['alternative_engine_url_candidates'],1)
            self.assertEqual(row['new_staged_files_from_alternative_engines'],1)
            catalog=json.loads((root/'stage/metadata/catalog.json').read_text())
            saved=catalog['albums'][0]['images'][0]
            self.assertEqual((root/'stage'/saved['key']).read_bytes(),incoming)
            self.assertEqual(saved['number'],2)
            self.assertEqual(report['remote_verified_files'],0)
            self.assertEqual(report['gallery_open_verified_files'],0)

    def test_repeated_bounded_runs_rotate_all_registered_public_pages(self):
        first='https://djawaphoto.com/portfolio/mimmi-work/'
        pages=[first+'?page='+str(i) for i in range(2,82)]
        cycles=[rotated_registered_page_queue(first,pages,21,i)[:21]
                for i in range(1,5)]
        self.assertTrue(all(chunk[0]==first for chunk in cycles))
        self.assertEqual(len(set(url for chunk in cycles for url in chunk)),81)
        self.assertEqual(rotated_registered_page_queue(first,pages,21,0),
                         [first]+pages)
        self.assertEqual(rotated_registered_page_queue(first,[first]+pages[:3],21,12),
                         [first]+pages[:3])
        with self.assertRaises(ValueError):
            rotated_registered_page_queue(first,pages,21,-1)

    def test_yui_artgravia_693_article_only_observed_native_same_volume(self):
        page='https://showartx.net/artgravia-vol-693-yui/'
        native='https://showartx.net/wp-content/uploads/2025/10/ART_693_75.jpg'
        variant='https://showartx.net/wp-content/uploads/2025/10/ART_693_75-768x576.jpg'
        second='https://showartx.net/wp-content/uploads/2025/10/ART_693_80.jpg'
        other='https://showartx.net/wp-content/uploads/2025/10/ART_684_15.jpg'
        raw=f'''<h1>Artgravia VOL.693 [Yui]</h1><article>
          <img src="{variant}"><a href="{native}"><img src="{variant}"></a>
          <img data-src="{second}">
          <img src="{other}">
          <img src="https://playartx.com/p/other/poster-thumb.jpg">
          <img src="https://showartx.net/wp-content/uploads/2025/10/ART_693_bn.jpg">
          </article><aside class="related"><img src="https://showartx.net/wp-content/uploads/2025/10/ART_693_21.jpg"></aside>'''
        photos,pages,status=page_images(raw,page,'yui')
        self.assertEqual(status,'scoped_public_page')
        self.assertEqual(photos,[native,second])
        self.assertEqual(pages,[])
        self.assertEqual(page_images(raw,page,'mimmi')[0],[])
        self.assertEqual(page_images(raw.replace('VOL.693','VOL.639'),page,'yui')[2],'missing_model_or_volume_context')
        self.assertEqual(page_images(raw,page.replace('693','684'),'yui')[2],'missing_model_or_volume_context')
        self.assertEqual(page_images('<h1>ArtGravia Vol.693 Yui</h1><article>Nothing</article>',page,'yui')[2],'no_public_photos')

    def test_artgravia_693_public_images_physically_staged_not_counted_from_84(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);base=root/'apps/yui-gallery';base.mkdir(parents=True)
            (base/'stored-albums.json').write_text('{"model":"yui","albums":[]}')
            source='https://showartx.net/artgravia-vol-693-yui/'
            url='https://showartx.net/wp-content/uploads/2025/10/ART_693_3.jpg'
            (base/'public-work-pages.json').write_text(json.dumps({'albums':[
                {'id':'artgravia-693-public','title':'ArtGravia Vol.693 Yui',
                 'source':source,'source_claimed_total_edition_photos':84}]}))
            raw=photo(20)
            owner={'schema_version':1,'model':'yui','albums':[
                {'id':'existing','images':[{'number':1,'sha256':'a'*64}]}]}
            class Client:
                calls=[]
                def get(self,u):
                    self.calls.append(u)
                    if u==source:return type('R',(),{'content':(
                        f'<h1>ArtGravia Vol.693 [Yui]</h1><article><img src="{url}"></article>').encode()})()
                    if u==url:return type('R',(),{'content':raw})()
                    raise AssertionError('Unobserved asset request')
            client=Client()
            result=collect(root,'yui',owner,root/'stage',10,4,client,album_ids=['artgravia-693-public'])
            self.assertEqual(result['new_local_individual_files'],1)
            visual_audit=json.loads((root/'stage/metadata/perceptual-duplicate-evidence.json').read_text())
            self.assertEqual(visual_audit['mode'],'evidence_only_no_gallery_mutation')
            self.assertEqual(visual_audit['files_scanned'],1)
            self.assertEqual(result['remote_verified_files'],0)
            self.assertEqual(client.calls,[source,url])
            catalog=json.loads((root/'stage/metadata/catalog.json').read_text())
            self.assertEqual(len(catalog['albums'][0]['images']),1)
            self.assertEqual(catalog['albums'][0]['images'][0]['sha256'],hashlib.sha256(raw).hexdigest())
            self.assertEqual(len(list((root/'stage/originals').rglob('*.jpg'))),1)

    def test_named_yui_work_images_are_exact_slug_and_prefix_scoped(self):
        cases=[
            ('meow','Meow','Yui_Meow_'),
            ('night-cat','Night Cat','NightCat_'),
            ('asuna-qipao','Asuna Qipao','Yui_Asuna-Qipao_'),
            ('summer','Summer','Yui_Sum_'),
            ('pure','Pure','Yui_pure_'),
            ('become-beautiful','Become Beautiful','yui_beautiful_'),
            ('night-training','Night Training','Yui_Night-Training_'),
        ]
        for slug,title,prefix in cases:
            with self.subTest(slug=slug):
                page='https://showartx.net/yui-'+slug+'/'
                native='https://showartx.net/wp-content/uploads/2026/03/'+prefix+'7.jpg'
                resized='https://showartx.net/wp-content/uploads/2026/03/'+prefix+'7-768x512.jpg'
                wrong='https://showartx.net/wp-content/uploads/2026/03/Yui_OTHER_2.jpg'
                html=(f'<h1>Yui – [{title}]</h1><article>'
                      f'<img src="{resized}"><a href="{native}"><img src="{resized}"></a>'
                      f'<img src="{wrong}"><img src="https://other.example/ev.jpg">'
                      '</article>')
                self.assertEqual(page_images(html,page,'yui'),([native],[],'scoped_public_page'))
                self.assertEqual(page_images(html,page,'mimmi')[0],[])
                self.assertEqual(page_images(html.replace(title,'Wrong Album'),page,'yui')[2],
                                 'missing_model_or_volume_context')

    def test_independent_origin_fallback_after_original_public_origin_403(self):
        source='https://showartx.net/artgravia-vol-677-yui/'
        alternate='https://www.nicesss.com/archives/mij/artgravia/469248.html'
        image='https://www.nicewww.com/wp-content/uploads/2026/05/1778813739-c81e728d9d4c2f6.jpg'
        unrelated='https://www.nicewww.com/wp-content/uploads/2026/05/not-the-same-work.jpg'
        raw=f'''<h1>ArtGravia – Vol.677 Yui(유이)</h1><article>
          <img src="{image}"><img src="{unrelated}">
          <aside class="related"><img src="{unrelated}"></aside></article>'''
        self.assertEqual(page_images(raw,alternate,'yui'),([image],[],'scoped_public_page'))
        # Live nicesss.com body carries sidebar-right even though the image
        # belongs to .entry-content. Global ancestor matching was rejecting it.
        wrapped=('<body class="post-template-default sidebar-right">'
                 '<div class="entry-content">'+raw+'</div></body>')
        self.assertEqual(page_images(wrapped,alternate,'yui'),([image],[],'scoped_public_page'))
        # The actual inner sidebar remains excluded.
        inner=wrapped.replace('</article>','<div class="related"><img src="'+image.replace('3739','9999')+'"></div></article>')
        self.assertEqual(page_images(inner,alternate,'yui'),([image],[],'scoped_public_page'))
        self.assertEqual(page_images(raw,alternate,'mimmi')[0],[])
        self.assertEqual(page_images(raw.replace('Vol.677','Vol.693'),alternate,'yui')[2],
                         'missing_model_or_volume_context')
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);base=root/'apps/yui-gallery';base.mkdir(parents=True)
            (base/'stored-albums.json').write_text('{"model":"yui","albums":[]}')
            (base/'public-work-pages.json').write_text(json.dumps({'albums':[{
                'id':'artgravia-677-yui-public-samples','title':'Yui ArtGravia Vol.677',
                'source':source,'source_pages':[alternate]}]}))
            owner={'schema_version':1,'model':'yui','albums':[
                {'id':'other-work','images':[{'number':1,'sha256':'b'*64}]}]}
            jpeg=photo(117)
            class Client:
                calls=[]
                def get(self,url):
                    self.calls.append(url)
                    if url==source:raise RuntimeError('Public source origin refuses GitHub runner')
                    if url==alternate:return type('R',(),{'content':raw.encode()})()
                    if url==image:return type('R',(),{'content':jpeg})()
                    raise AssertionError('Only exact user-visible assets can be requested')
            client=Client()
            result=collect(root,'yui',owner,root/'stage',3,3,client,album_ids=['artgravia-677-yui-public-samples'])
            self.assertEqual(result['new_local_individual_files'],1)
            self.assertEqual(client.calls,[source,alternate,image])
            self.assertEqual(len(list((root/'stage/originals').rglob('*.jpg'))),1)
            self.assertEqual(result['remote_verified_files'],0)

    def test_publisher_article_keeps_photos_when_global_body_has_sidebar_class(self):
        page='https://djawaphoto.com/portfolio/mimmi-sample/'
        image='https://djawaphoto.com/wp-content/uploads/2026/10/mimmi-sample01.jpg'
        related='https://djawaphoto.com/wp-content/uploads/2026/10/mimmi-related02.jpg'
        html=(f'<body class="single sidebar-right"><h1>DJAWA Mimmi photo sample</h1>'
              f'<article><img src="{image}"><div class="related"><img src="{related}"></div>'
              '</article></body>')
        pictures,pages,status=page_images(html,page,'mimmi')
        self.assertEqual(status,'scoped_public_page')
        self.assertEqual(pictures,[image])
        self.assertEqual(pages,[])
        self.assertEqual(page_images(html,page,'yui')[2],'missing_model_context')

    def test_v2ph_public_first_page_and_login_stop(self):
        page='https://www.v2ph.com/album/a887785a.html'
        first='https://cdn.v2ph.com/photos/A12345678.jpg'
        second='https://cdn.v2ph.com/photos/B12345678.jpg'
        raw=f'''<h1>[DJAWA] Mimmi - cosplay</h1>
          <div class="photo-gallery">
            <a href="{first}"><img src="{first}"></a>
            <img data-src="{second}">
          </div>
          <aside class="related"><img src="https://cdn.v2ph.com/photos/UNRELATED99.jpg"></aside>
          <a href="?page=2">Next</a><a href="/album/other.html">Other gallery</a>'''
        urls,pages,status=page_images(raw,page,'mimmi')
        self.assertEqual(status,'scoped_public_page')
        self.assertEqual(urls,[first,second])
        self.assertEqual(pages,[page+'?page=2'])
        self.assertEqual(page_images(raw,page,'yui')[2],'missing_model_context')
        login='<h1>Mimmi - Page 2</h1><p>You need to log in to view more content of this album.</p>'
        self.assertEqual(page_images(login,page+'?page=2','mimmi'),
                         ([],[],'login_required_for_additional_pages'))

    def test_targeted_v2ph_photo_is_stored_as_individual_file(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);base=root/'apps/mimmi-gallery';base.mkdir(parents=True)
            (base/'stored-albums.json').write_text('{"model":"mimmi","albums":[]}')
            source='https://www.v2ph.com/album/a887785a.html'
            url='https://cdn.v2ph.com/photos/A12345678.jpg'
            (base/'v2ph-actor-previews.json').write_text(json.dumps({'albums':[
                {'id':'focus-work','title':'Mimmi focus','source':source},
                {'id':'untouched-work','title':'Other Mimmi','source':source}]}))
            existing=photo(1);fresh=photo(30)
            owner={'schema_version':1,'model':'mimmi','albums':[
                {'id':'another-existing','images':[{'number':1,'sha256':hashlib.sha256(existing).hexdigest()}]}]}
            class Client:
                calls=[]
                def get(self,u):
                    self.calls.append(u)
                    if u==source:
                        return type('R',(),{'content':f'<h1>Mimmi</h1><a href="{url}"><img src="{url}"></a>'.encode()})()
                    if u==url:return type('R',(),{'content':fresh})()
                    raise AssertionError('Out-of-scope URL')
            client=Client()
            result=collect(root,'mimmi',owner,root/'stage',3,2,client,album_ids=['focus-work'])
            self.assertEqual(result['new_local_individual_files'],1)
            self.assertEqual(client.calls,[source,url])
            album=json.loads((root/'stage/metadata/catalog.json').read_text())['albums'][0]
            self.assertEqual(album['id'],'focus-work')
            self.assertEqual(album['images'][0]['sha256'],hashlib.sha256(fresh).hexdigest())
            self.assertFalse(list((root/'stage').rglob('*.zip')))

    def test_provider_verification_hold_does_not_redownload_or_reupload_the_work(self):
        with tempfile.TemporaryDirectory() as name:
            root=Path(name);base=root/'apps/mimmi-gallery';base.mkdir(parents=True)
            (base/'stored-albums.json').write_text('{"model":"mimmi","albums":[]}')
            (base/'public-work-pages.json').write_text(json.dumps({'albums':[{
                'id':'held-work','source':'https://djawaphoto.com/portfolio/mimmi-held/',
                'storage_verification_hold':True,'visual_reference_required':True}]}))
            owner={'schema_version':1,'model':'mimmi','albums':[{'id':'held-work','images':[{'number':1,'sha256':'a'*64}]}]}
            class Client:
                def get(self,url):raise AssertionError('A challenged work must not be collected again')
            report=collect(root,'mimmi',owner,root/'stage',5,3,Client())
            self.assertEqual(report['new_local_individual_files'],0)
            self.assertTrue(report['results'][0]['storage_verification_required'])
            self.assertTrue(report['results'][0]['source_not_redownloaded'])

    def test_declared_individual_public_edition_excludes_other_models_and_hosts(self):
        page='https://www.shypetal.com/albums/mimmi-public-work/'
        images=[f'https://image.shypetal.com/image/Mimmi_Work/ShyPetal.com@-{n:03d}.webp' for n in (1,2,3)]
        raw=f'''<h1>Mimmi public work</h1><div data-images='{json.dumps(images)}'></div>
                <aside><img src="https://image.shypetal.com/image/Other/ShyPetal.com@-001.webp"></aside>'''
        self.assertEqual(page_images(raw,page,'mimmi'),(images,[],'scoped_public_page'))
        self.assertEqual(page_images(raw,page,'yui')[0],[])
        self.assertEqual(page_images(raw.replace('image.shypetal.com/image/Mimmi_Work','evil.invalid/image/Mimmi_Work'),page,'mimmi')[0],[])
        mixed=raw.replace('Mimmi_Work/ShyPetal.com@-003','Other_Work/ShyPetal.com@-003')
        self.assertEqual(page_images(mixed,page,'mimmi')[2],'mixed_public_editions_rejected')

    def test_verified_creator_feed_can_scan_entire_known_corpus_without_unbounded_fetch(self):
        from direct_photo_pipeline import verified_creator_feed_candidates
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);rows=[{
                'source':'official-sns',
                'post':f'https://x.com/super_yuisan/status/{2117242902825091424+i}',
                'url':f'https://pbs.twimg.com/media/OfficialCut{i:04d}.jpg?name=orig'}
                for i in range(75)]
            (root/'feed.json').write_text(json.dumps({
                'source':'https://teapawt.net/super_yuisan/media','images':rows}))
            full=verified_creator_feed_candidates(root,page_cycle=3,max_urls=75)
            self.assertEqual(len(full),75)
            self.assertEqual(set(full),{x['url'] for x in rows})
            self.assertEqual(len(verified_creator_feed_candidates(root,page_cycle=3)),40)
            with self.assertRaises(ValueError):
                verified_creator_feed_candidates(root,max_urls=501)

    def test_official_yui_feed_link_is_downloaded_as_real_individual_file(self):
        from direct_photo_pipeline import verified_creator_feed_candidates
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);base=root/'apps/yui-gallery';base.mkdir(parents=True)
            (base/'stored-albums.json').write_text('{"model":"yui","albums":[]}')
            page='https://teapawt.net/super_yuisan'
            previous='https://pbs.twimg.com/media/ExistingPhoto123.jpg?name=orig'
            fresh='https://pbs.twimg.com/media/NewPhotoABCDE.jpg?name=orig'
            wrong='https://pbs.twimg.com/media/OtherPhotoXYZ.jpg?name=orig'
            (base/'public-work-pages.json').write_text(json.dumps({'albums':[{
                'id':'public-yui-sns','title':'Yui official SNS',
                'source':page}]}))
            (base/'feed.json').write_text(json.dumps({
                'source':'https://teapawt.net/super_yuisan/media',
                'images':[
                    {'source':'official-sns','post':'https://x.com/super_yuisan/status/2117242902825091424','url':fresh},
                    {'source':'official-sns','post':'https://x.com/other/status/2117242902825091424','url':wrong},
                    {'source':'mirror','post':'https://x.com/super_yuisan/status/2117242902825091425','url':wrong},
                    {'source':'official-sns','post':'https://x.com/super_yuisan/status/2117242902825091424','url':fresh}]}))
            self.assertEqual(verified_creator_feed_candidates(base),[fresh])
            already=photo(2);new=photo(33)
            owner={'schema_version':1,'model':'yui','albums':[{
                'id':'public-yui-sns','images':[{
                    'number':1,'sha256':hashlib.sha256(already).hexdigest()}]}]}
            class Client:
                calls=[]
                def get(self,url):
                    self.calls.append(url)
                    if url==page:
                        body=f'<div class="timeline-item" data-username="super_yuisan"><img src="{previous}"></div>'
                        return type('R',(),{'content':body.encode()})()
                    if url==previous:data=already
                    elif url==fresh:data=new
                    else:raise AssertionError('Untrusted media must not be fetched: '+url)
                    return type('R',(),{'content':data})()
            client=Client()
            report=collect(root,'yui',owner,root/'stage',3,2,client,
                           reviewed_source_only=True)
            self.assertEqual(report['new_local_individual_files'],1)
            self.assertEqual(report['results'][0]['official_creator_feed_candidates_added'],1)
            self.assertNotIn(wrong,client.calls)
            catalog=json.loads((root/'stage/metadata/catalog.json').read_text())
            row=catalog['albums'][0]['images'][0]
            self.assertEqual((root/'stage'/row['key']).read_bytes(),new)
            self.assertEqual(row['sha256'],hashlib.sha256(new).hexdigest())

    def test_previous_official_creator_feed_uses_independent_public_media_when_timeline_held(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);base=root/'apps/yui-gallery';base.mkdir(parents=True)
            (base/'stored-albums.json').write_text('{"model":"yui","albums":[]}')
            source='https://teapawt.net/super_yuisan'
            media='https://pbs.twimg.com/media/IndependentlyPublicABC.jpg?name=orig'
            (base/'public-work-pages.json').write_text(json.dumps({'albums':[{
                'id':'public-yui-sns','title':'Yui public SNS','source':source}]}))
            (base/'feed.json').write_text(json.dumps({
                'source':'https://teapawt.net/super_yuisan/media','images':[{
                    'source':'official-sns',
                    'post':'https://x.com/super_yuisan/status/2117242902825091424',
                    'url':media}]}))
            original=photo(9);new=photo(69)
            owner={'schema_version':1,'model':'yui','albums':[{
                'id':'public-yui-sns','images':[{
                    'number':1,'sha256':hashlib.sha256(original).hexdigest()}]}]}
            class Client:
                def __init__(self):
                    self.blocked_origins={'https://teapawt.net'};self.calls=[]
                def get(self,url):
                    self.calls.append(url)
                    if url!=media:raise AssertionError('Held timeline must not be accessed')
                    return type('R',(),{'content':new})()
            client=Client()
            report=collect(root,'yui',owner,root/'stage',3,2,client,
                           reviewed_source_only=True)
            self.assertEqual(client.calls,[media])
            self.assertEqual(report['new_local_individual_files'],1)
            self.assertEqual(report['results'][0]['blocked_origin_pages_not_retried'],1)
            self.assertEqual(report['results'][0]['official_creator_feed_candidates_added'],1)
            catalog=json.loads((root/'stage/metadata/catalog.json').read_text())
            row=catalog['albums'][0]['images'][0]
            self.assertEqual((root/'stage'/row['key']).read_bytes(),new)
            self.assertEqual(len((root/'stage/journal.jsonl').read_text().splitlines()),1)

    def test_public_media_origin_pause_skips_repeated_denied_downloads(self):
        from public_photo_archive import PublicOriginPaused
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);base=root/'apps/yui-gallery';base.mkdir(parents=True)
            (base/'stored-albums.json').write_text('{"model":"yui","albums":[]}')
            page='https://teapawt.net/super_yuisan'
            media=[f'https://pbs.twimg.com/media/OriginalTest{i:02d}.jpg?name=orig' for i in range(3)]
            (base/'public-work-pages.json').write_text(json.dumps({'albums':[{
                'id':'public-yui-sns','title':'Yui official SNS','source':page}]}))
            (base/'feed.json').write_text(json.dumps({
                'source':'https://teapawt.net/super_yuisan/media','images':[
                    {'source':'official-sns',
                     'post':f'https://x.com/super_yuisan/status/211724290282509142{i}',
                     'url':u} for i,u in enumerate(media)]}))
            owner={'schema_version':1,'model':'yui','albums':[{
                'id':'public-yui-sns','images':[{
                    'number':1,'sha256':hashlib.sha256(photo(0)).hexdigest()}]}]}
            class Client:
                def __init__(self):self.blocked_origins=set();self.calls=[]
                def get(self,url):
                    self.calls.append(url)
                    if url==page:
                        html=f'<div class="timeline-item" data-username="super_yuisan"><img src="{media[0]}"></div>'
                        return type('R',(),{'content':html.encode()})()
                    self.blocked_origins.add('https://pbs.twimg.com')
                    raise PublicOriginPaused(403,'access_denied')
            client=Client()
            report=collect(root,'yui',owner,root/'stage',3,2,client,
                           reviewed_source_only=True)
            self.assertEqual(client.calls,[media[0],page])
            self.assertEqual(report['results'][0]['failure_categories'],{'PublicOriginPaused':1})
            self.assertEqual(report['results'][0]['media_candidates_deferred_after_origin_pause'],2)
            self.assertEqual(report['new_local_individual_files'],0)

    def test_creator_feed_keeps_observed_original_and_rejects_quote_media(self):
        page='https://teapawt.net/super_yuisan'
        own='https://pbs.twimg.com/media/OwnPhoto1234.jpg?name=orig'
        other='https://pbs.twimg.com/media/OtherPhoto1234.jpg?name=orig'
        raw=f'''<div class="timeline-item" data-username="super_yuisan">
          <img src="{own}"><div class="quote"><img src="{other}"></div>
          <div class="timeline-item" data-username="other"><img src="{other}"></div></div>
          <a href="/super_yuisan?cursor=observed">Load more</a>'''
        urls,pages,status=page_images(raw,page,'yui')
        self.assertEqual(urls,[own]);self.assertEqual(pages,[page+'?cursor=observed'])
        self.assertEqual(status,'scoped_public_page')
        self.assertEqual(page_images(raw,page,'mimmi')[0],[])

    def test_legacy_observed_pages_recover_only_curated_existing_work(self):
        with tempfile.TemporaryDirectory() as name:
            root=Path(name);base=root/'apps/yui-gallery';base.mkdir(parents=True)
            (base/'stored-albums.json').write_text('{"model":"yui","albums":[]}')
            page='https://www.inven.co.kr/board/webzine/2097/123'
            known='https://upload3.inven.co.kr/known.jpg'
            other='https://upload3.inven.co.kr/other-model.jpg'
            raw=photo(31)
            record={'number':2,'url':known,'sha256':hashlib.sha256(raw).hexdigest(),
                    'bytes':len(raw),'width':400,'height':600}
            albums=[{'id':'legacy-work','source_pages':['https://unreviewed.invalid/page',page],
                     'images':[record]},
                    {'id':'previously-removed-work','source_pages':[page],'images':[record]}]
            (base/'additional-source-albums.json').write_text(json.dumps({'albums':albums}))
            owner={'schema_version':1,'model':'yui','albums':[{'id':'legacy-work',
                   'images':[{'number':1,'sha256':hashlib.sha256(photo(0)).hexdigest()}]}]}
            class Client:
                calls=[]
                def get(self,url):
                    self.calls.append(url)
                    if url==page:
                        data=f'<title>심유이 행사</title><article>여러 모델 <img src="{known}"><img src="{other}"></article>'.encode()
                    elif url==known:data=raw
                    else:raise AssertionError('Must not request unreviewed images or hosts')
                    return type('Response',(),{'content':data})()
            client=Client();report=collect(root,'yui',owner,root/'stage',5,3,client)
            self.assertEqual(report['new_local_individual_files'],1)
            self.assertEqual(client.calls,[page,known])
            self.assertEqual(len(report['results']),1,'Removed works must stay removed')
            self.assertEqual(report['results'][0]['unreviewed_legacy_image_candidates_skipped'],1)
            saved=json.loads((root/'stage/metadata/catalog.json').read_text())['albums'][0]
            self.assertEqual(saved['id'],'legacy-work');self.assertEqual(saved['images'][0]['number'],2)

    def test_full_public_variant_replaces_proven_same_slot_only(self):
        with tempfile.TemporaryDirectory() as name:
            root=Path(name);base=root/'apps/yui-gallery';base.mkdir(parents=True)
            (base/'stored-albums.json').write_text('{"model":"yui","albums":[]}')
            fresh=photo(0);buf=BytesIO()
            with Image.open(BytesIO(fresh)) as im:im.resize((300,450)).save(buf,format='JPEG',quality=90)
            old=buf.getvalue();oldsha=hashlib.sha256(old).hexdigest()
            url='https://upload3.inven.co.kr/photo.jpg?MW=300';page='https://www.inven.co.kr/board/webzine/2097/123'
            row={'number':1,'url':url,'sha256':oldsha,'bytes':len(old),'width':300,'height':450}
            (base/'additional-source-albums.json').write_text(json.dumps({'albums':[{'id':'public-board','source':page,'images':[row]}]}))
            owner={'schema_version':1,'model':'yui','albums':[{'id':'public-board','images':[row]}]}
            class Client:
                def get(self,u):
                    data=(f'<title>심유이 사진</title><div id="powerbbsContent"><img src="{url}"></div>'.encode()
                          if u==page else old if u==url else fresh)
                    return type('Response',(),{'content':data})()
            report=collect(root,'yui',owner,root/'stage',2,2,Client())
            self.assertEqual(report['higher_resolution_replacements'],1)
            self.assertEqual(report['new_photo_positions'],0)
            p=json.loads((root/'stage/metadata/catalog.json').read_text())['albums'][0]['images'][0]
            self.assertEqual(p['number'],1);self.assertEqual(p['variant_of_sha256'],oldsha)
            updated={**owner,'albums':[{'id':'public-board','images':[p]}]}
            again=collect(root,'yui',updated,root/'second-stage',2,2,Client())
            self.assertEqual(again['new_local_individual_files'],0)
            self.assertFalse(again['results'][0]['failures'],'Already proven higher-resolution originals must remain idempotent')

    def test_public_width_variant_and_scoped_board(self):
        raw='''<title>심유이 공개 사진</title><article><div id="powerbbsContent">
        <img src="https://upload3.inven.co.kr/a.jpg?MW=800"></div>
        <aside><img src="https://upload3.inven.co.kr/other.jpg"></aside></article>'''
        urls,_,_=page_images(raw,'https://www.inven.co.kr/board/webzine/2097/123','yui')
        self.assertEqual(urls,['https://upload3.inven.co.kr/a.jpg'])
        self.assertEqual(public_full_variant('https://cdn.v2ph.com/a.jpg?MW=800'),'https://cdn.v2ph.com/a.jpg?MW=800')
        self.assertTrue(same_variant(photo(0),photo(0)))
        self.assertFalse(same_variant(photo(0),photo(100)))

    def test_scope_original_links_pagination_and_other_models(self):
        page='https://djawaphoto.com/portfolio/mimmi-book/'
        raw='''<h1>Mimmi book</h1><article>Mimmi
          <a href="/wp-content/uploads/photo.jpg"><img src="/wp-content/uploads/photo-3000x4500.jpg"></a>
          <aside class="related"><img src="/wp-content/uploads/other.jpg"></aside>
          <a rel="next" href="?page=2">Next</a></article>'''
        urls,pages,status=page_images(raw,page,'mimmi')
        self.assertEqual(urls,['https://djawaphoto.com/wp-content/uploads/photo.jpg'])
        self.assertEqual(pages,[page+'?page=2'])
        self.assertEqual(page_images(raw.replace('Mimmi','Other'),page,'mimmi')[0],[])

    def test_flat_error_image_and_damaged_data_rejected(self):
        data=BytesIO();Image.new('RGB',(1200,1800),'white').save(data,format='PNG')
        with self.assertRaises(ValueError):inspect(data.getvalue())
        with self.assertRaises(Exception):inspect(b'not an actual photograph'*1000)

    def test_individual_bytes_resume_and_no_bundle(self):
        with tempfile.TemporaryDirectory() as name:
            root=Path(name);base=root/'apps/mimmi-gallery';base.mkdir(parents=True)
            (base/'stored-albums.json').write_text('{"model":"mimmi","albums":[]}')
            page='https://djawaphoto.com/portfolio/mimmi-book/'
            (base/'official-previews.json').write_text(json.dumps({'albums':[{'id':'mimmi-book','title':'Mimmi book','source':page}]}))
            old=photo(0);fresh=photo(31)
            owner={'schema_version':1,'model':'mimmi','albums':[{'id':'mimmi-book','images':[{'number':1,'sha256':hashlib.sha256(old).hexdigest()}]}]}
            target='https://djawaphoto.com/wp-content/uploads/fresh.jpg'
            class Client:
                calls=[]
                def get(self,url):
                    self.calls.append(url)
                    content=(f'<article>Mimmi <a href="{target}">full photo</a></article>'.encode() if url==page else fresh)
                    return type('Response',(),{'content':content})()
            client=Client();out=root/'stage'
            report=collect(root,'mimmi',owner,out,1,2,client)
            self.assertEqual(report['new_local_individual_files'],1)
            manifest=json.loads((out/'metadata/catalog.json').read_text());p=manifest['albums'][0]['images'][0]
            self.assertEqual((out/p['key']).read_bytes(),fresh)
            self.assertEqual(p['number'],2)
            self.assertEqual(p['numbering_provenance'],'archive_append_order_not_publisher_number')
            self.assertEqual(list(out.rglob('*.zip')),[])
            before=len(client.calls);again=collect(root,'mimmi',owner,out,1,2,client)
            self.assertEqual(again['downloaded_new_this_invocation'],0)
            self.assertEqual(again['resumed_verified_staged_files'],1)
            self.assertEqual(len(client.calls),before)
            (out/p['key']).write_bytes(b'corrupted')
            with self.assertRaises(ValueError):collect(root,'mimmi',owner,out,1,2,client)


if __name__=='__main__':unittest.main(verbosity=2)
