import hashlib
import tempfile
import unittest
from unittest.mock import patch,MagicMock
from pathlib import Path

from test_direct_photo_pipeline import photo
from visual_public_work import collect_work,visual_error,owner_reference


class VisualWorkTests(unittest.TestCase):
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
            client.omit=True
            partial,coverage=collect_work(book,prior,client,out,5,{p['sha256'] for p in prior},'mimmi',lambda u:client.get(u).content)
            self.assertEqual([p['source_photo_number'] for p in partial['images']],[4])
            self.assertEqual(coverage['unresolved_source_numbers'],[5])
            self.assertFalse(coverage['source_edition_all_files_accounted_for'])
            client.omit=False;client.corrupt=True
            # Cached verified reference bytes remain acceptable. A new empty
            # stage must reject the corrupted remote response.
            self.assertIsNone(collect_work(book,prior,client,out/'fresh',5,saved,'mimmi',lambda u:client.get(u).content)[0])
            self.assertEqual(list(out.rglob('*.zip')),[])

    def test_different_picture_is_not_visual_duplicate(self):
        self.assertLess(visual_error(photo(0),photo(0)),.01)
        self.assertGreater(visual_error(photo(0),photo(120)),9)


if __name__=='__main__':unittest.main(verbosity=2)
