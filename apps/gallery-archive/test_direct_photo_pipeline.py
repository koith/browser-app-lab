import hashlib
from io import BytesIO
import json
from pathlib import Path
import tempfile
import unittest
from PIL import Image
from direct_photo_pipeline import collect, inspect, page_images, same_variant, public_full_variant


def photo(seed):
    im=Image.new('RGB',(400,600))
    im.putdata([((x*7+seed)%256,(y*11+seed)%256,((x+y)*13+seed)%256) for y in range(600) for x in range(400)])
    buf=BytesIO();im.save(buf,format='JPEG',quality=93);return buf.getvalue()


class DirectTests(unittest.TestCase):
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
