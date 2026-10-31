import hashlib
import tempfile
import unittest
from unittest.mock import patch,MagicMock
from pathlib import Path

from test_direct_photo_pipeline import photo
from visual_public_work import collect_work,visual_error,owner_reference


class VisualWorkTests(unittest.TestCase):
    def test_count_alone_never_claims_complete_edition(self):
        book={'id':'saved-work','source':'https://www.shypetal.com/albums/saved-work/',
              'public_web_edition_photos':3}
        previous=[{'sha256':str(i)*64} for i in (1,2,3)]
        work,info=collect_work(book,previous,None,Path('/unused'),5,set(),'mimmi')
        self.assertIsNone(work);self.assertTrue(info['deferred_for_source_coverage_review'])
        self.assertNotIn('already_saved_web_edition',info)

    def test_independent_declared_public_files_keep_numbers_without_bundle_download(self):
        import json
        with tempfile.TemporaryDirectory() as temporary:
            data={n:photo(seed) for n,seed in enumerate((0,40,80,140,210),1)}
            previous=[{'number':n,'sha256':hashlib.sha256(data[n]).hexdigest(),
                       'width':800,'height':1200} for n in (1,2,3)]
            page='https://www.shypetal.com/albums/mimmi-fixture/'
            urls=[f'https://image.shypetal.com/image/Mimmi_Fixture/ShyPetal.com@-{n:03d}.webp' for n in range(1,6)]
            class Client:
                def get(self,url):
                    if url==page:
                        raw=f'''<h1>Mimmi fixture</h1><div data-images='{json.dumps(urls)}'></div>
                                <a href="/never-fetch.zip">Download ZIP</a>'''.encode()
                    elif url in urls:raw=data[urls.index(url)+1]
                    else:raise AssertionError('Only declared individual public images may be fetched')
                    return type('Response',(),{'content':raw})()
            book={'id':'mimmi-fixture','title':'Mimmi fixture','source':page,'public_web_edition_photos':5}
            client=Client();out=Path(temporary)
            work,info=collect_work(book,previous,client,out,5,{p['sha256'] for p in previous},'mimmi',
                                   lambda url:data[int(url.split('/')[-2])])
            self.assertEqual(info['saved_reference_anchors'],3)
            self.assertEqual(info['source_files_decoded'],5)
            self.assertEqual(info['unresolved_source_numbers'],[])
            self.assertEqual([p['source_photo_number'] for p in work['images']],[4,5])
            self.assertEqual(list(out.rglob('*.zip')),[])

            # Legacy preview metadata can be shared by distinct originals.
            # An original fallback must not collide in that preview's cache.
            shared=[{**p,'preview_sha256':'9'*64} for p in previous]
            recovered=out/'shared-preview-cache';cache=recovered/'references'/'mimmi-fixture'
            cache.mkdir(parents=True);stale=cache/('9'*64+'.bin');stale.write_bytes(data[1])
            complete,info=collect_work(book,shared,client,recovered,5,
                {p['sha256'] for p in shared},'mimmi',lambda url:data[int(url.split('/')[-2])])
            self.assertEqual(info['saved_reference_anchors'],3)
            self.assertEqual(len(complete['images']),2)
            self.assertEqual(stale.read_bytes(),data[1])
            for p in shared:
                self.assertEqual((cache/(p['sha256']+'.bin')).read_bytes(),data[p['number']])

    def test_owner_api_reader_is_fixed_no_auth_and_no_redirects(self):
        with patch('visual_public_work.requests.get') as get:
            response=MagicMock();response.status_code=200;response.iter_content.return_value=[b'owner bytes']
            get.return_value.__enter__.return_value=response
            url='https://mimmi-private-gallery-free.onrender.com/api/media/saved-work/1/preview'
            self.assertEqual(owner_reference(url),b'owner bytes')
            self.assertEqual(get.call_args.kwargs,{'timeout':(12,45),'allow_redirects':False,'stream':True})
            response.status_code=302
            with self.assertRaises(ValueError):owner_reference(url)
            before=get.call_count
            for rejected in ['https://example.org/private.jpg',url+'?token=secret',url.replace('https:','http:')]:
                with self.assertRaises(ValueError):owner_reference(rejected)
            self.assertEqual(get.call_count,before)

    def test_full_edition_saved_anchors_and_no_duplicate_pose_or_downgrade(self):
        with tempfile.TemporaryDirectory() as temporary:
            data={n:photo(seed) for n,seed in enumerate((0,40,80,140,210),1)}
            prior=[{'number':n,'sha256':hashlib.sha256(data[n]).hexdigest(),
                    'preview_sha256':hashlib.sha256(data[n]).hexdigest(),'width':800,'height':1200} for n in (1,2,3)]
            prior.append({**prior[2],'number':8})
            page='https://sexy.pixibb.com/mimmi-fixture/'
            class Client:
                omit=False;corrupt=False
                def get(self,url):
                    if url==page:
                        raw=('<article><h1>Mimmi fixture</h1>'+''.join(
                            f'<img src="https://images08.pixibb.com/Mimmi-PixiBB.COM-{n:03d}.jpg">' for n in range(1,5 if self.omit else 6))+'</article>').encode()
                    elif '/api/media/' in url:
                        raw=data[int(url.split('/')[-2])]
                        if self.corrupt:raw=b'corrupt reference'
                    else:raw=data[int(url.rsplit('-',1)[1].split('.')[0])]
                    return type('Response',(),{'content':raw})()
            book={'id':'mimmi-fixture','title':'Mimmi fixture','source':page,'public_web_edition_photos':5}
            saved={p['sha256'] for p in prior};out=Path(temporary);client=Client()
            work,report=collect_work(book,prior,client,out,5,saved,'mimmi',lambda u:client.get(u).content)
            self.assertEqual(report['saved_reference_anchors'],3)
            self.assertEqual([p['number'] for p in work['images']],[9,10])
            self.assertEqual([p['source_photo_number'] for p in work['images']],[4,5])
            for row in work['images']:
                self.assertEqual((out/row['key']).read_bytes(),data[row['source_photo_number']])
                self.assertEqual(row['key'],f"originals/mimmi-fixture/{row['sha256']}.jpg")
                self.assertEqual(row['preview'],f"previews/mimmi-fixture/{row['preview_sha256']}.webp")
            client.omit=True
            partial,coverage=collect_work(book,prior,client,out,5,{p['sha256'] for p in prior},'mimmi',lambda u:client.get(u).content)
            self.assertEqual([p['source_photo_number'] for p in partial['images']],[4])
            self.assertEqual(coverage['unresolved_source_numbers'],[5])
            self.assertFalse(coverage['source_edition_all_files_accounted_for'])
            client.omit=False;client.corrupt=True
            # Cached verified reference bytes remain acceptable. A new empty
            # stage must reject the corrupted remote response.
            self.assertIsNone(collect_work(book,prior,client,out/'fresh',5,saved,'mimmi',lambda u:client.get(u).content)[0])
            local={}
            for n in (1,2,3):
                path=out/(str(n)+'.jpg');path.write_bytes(data[n]);local[prior[n-1]['sha256']]=path
            def unavailable(url):raise RuntimeError('Owner API unavailable')
            work,info=collect_work(book,prior,client,out/'from-local',5,{p['sha256'] for p in prior},'mimmi',unavailable,local)
            self.assertEqual(len(work['images']),2)
            local[prior[0]['sha256']].write_bytes(b'corrupted local reference')
            self.assertIsNone(collect_work(book,prior,client,out/'bad-local',5,saved,'mimmi',unavailable,local)[0])
            client.corrupt=False;reads=[]
            def existing_owner(url):
                reads.append(url);return client.get(url).content
            work,info=collect_work(book,prior,client,out/'local-repaired-from-owner',5,
                {p['sha256'] for p in prior},'mimmi',existing_owner,local)
            self.assertEqual(len(work['images']),2)
            self.assertEqual(info['stale_local_reference_numbers'],[1])
            self.assertEqual(len(reads),1)
            self.assertEqual(list(out.rglob('*.zip')),[])

    def test_different_picture_is_not_visual_duplicate(self):
        self.assertLess(visual_error(photo(0),photo(0)),.01)
        self.assertGreater(visual_error(photo(0),photo(120)),9)


if __name__=='__main__':unittest.main(verbosity=2)
