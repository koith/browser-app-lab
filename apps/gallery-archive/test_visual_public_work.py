import hashlib
import tempfile
import unittest
from pathlib import Path

from test_direct_photo_pipeline import photo
from visual_public_work import collect_work,visual_error


class VisualWorkTests(unittest.TestCase):
    def test_full_edition_saved_anchors_and_no_duplicate_pose_or_downgrade(self):
        with tempfile.TemporaryDirectory() as temporary:
            data={n:photo(seed) for n,seed in enumerate((0,40,80,140,210),1)}
            prior=[{'number':n,'sha256':hashlib.sha256(data[n]).hexdigest(),
                    'preview_sha256':hashlib.sha256(data[n]).hexdigest(),'width':800,'height':1200} for n in (1,2,3)]
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
            work,report=collect_work(book,prior,client,out,5,saved,'mimmi')
            self.assertEqual(report['saved_reference_anchors'],3)
            self.assertEqual([p['number'] for p in work['images']],[4,5])
            self.assertEqual([p['source_photo_number'] for p in work['images']],[4,5])
            for row in work['images']:
                self.assertEqual((out/row['key']).read_bytes(),data[row['source_photo_number']])
            client.omit=True
            self.assertIsNone(collect_work(book,prior,client,out,5,saved,'mimmi')[0])
            client.omit=False;client.corrupt=True
            # Cached verified reference bytes remain acceptable. A new empty
            # stage must reject the corrupted remote response.
            self.assertIsNone(collect_work(book,prior,client,out/'fresh',5,saved,'mimmi')[0])
            self.assertEqual(list(out.rglob('*.zip')),[])

    def test_different_picture_is_not_visual_duplicate(self):
        self.assertLess(visual_error(photo(0),photo(0)),.01)
        self.assertGreater(visual_error(photo(0),photo(120)),9)


if __name__=='__main__':unittest.main(verbosity=2)
