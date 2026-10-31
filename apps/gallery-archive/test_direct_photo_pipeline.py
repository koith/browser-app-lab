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
