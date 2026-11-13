import hashlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from PIL import Image

from recover_recorded_public_photo_bytes import candidates, recover, validated

class RecoveryTests(unittest.TestCase):
    def test_historical_source_exact_sha_only_and_real_stored_file(self):
        data=io.BytesIO()
        Image.new('RGB',(700,1050),(93,121,151)).save(data,format='JPEG')
        raw=data.getvalue()
        sha=hashlib.sha256(raw).hexdigest()
        source='https://www.v2ph.com/album/a54385nz.html'
        url='https://cdn.v2ph.com/photos/abcdefABCDEF1234.jpg'
        row={'url':url,'bytes':len(raw),'sha256':sha,'width':700,'height':1050}
        self.assertTrue(validated(row,'v2ph',source))
        self.assertFalse(validated(row,'v2ph','https://evil.example/album/a54385nz.html'))
        self.assertFalse(validated({**row,'url':'https://evil.example/picture.jpg'},'v2ph',source))
        self.assertFalse(validated({**row,'sha256':'0'*64},'official',source))
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);base=root/'apps/mimmi-gallery';base.mkdir(parents=True)
            (base/'owner-index.json').write_text(json.dumps({
                'model':'mimmi','albums':[{'id':'existing','images':[]}]}))
            (base/'stored-albums.json').write_text(json.dumps({
                'model':'mimmi','albums':[],'physical_verified_image_count':0}))
            (base/'v2ph-actor-previews.json').write_text(json.dumps({'albums':[{
                'id':'v2ph-actor-a54385nz','title':'Mimmi — Rudy','source':source,
                'samples':[row]}]}))
            class Stub:
                def __init__(self, body):self.body=body
                def get(self,request):
                    assert request==url
                    return type('Response',(),{'content':self.body})()
            new=recover(root,'v2ph',max_new=9,max_bytes=4_000_000,client=Stub(raw))
            self.assertEqual(new['real_physical_new_sha'],1)
            saved=json.loads((base/'stored-albums.json').read_text())
            photo=saved['albums'][0]['images'][0]
            self.assertEqual(saved['physical_verified_image_count'],1)
            self.assertEqual(hashlib.sha256((base/photo['url']).read_bytes()).hexdigest(),sha)
            repeat=recover(root,'v2ph',max_new=9,max_bytes=4_000_000,client=Stub(raw))
            self.assertEqual(repeat['real_physical_new_sha'],0)
            self.assertEqual(len(json.loads((base/'stored-albums.json').read_text())['albums'][0]['images']),1)
            # Different source bytes cannot poison the original archive.
            (base/'stored-albums.json').write_text(json.dumps({
                'model':'mimmi','albums':[],'physical_verified_image_count':0}))
            another=io.BytesIO()
            Image.new('RGB',(700,1050),(92,121,151)).save(another,format='JPEG')
            bad=recover(root,'v2ph',max_new=9,max_bytes=4_000_000,client=Stub(another.getvalue()))
            self.assertEqual(bad['real_physical_new_sha'],0)
            self.assertEqual(bad['statistics']['not_historical_sha'],1)
            self.assertFalse(json.loads((base/'stored-albums.json').read_text())['albums'])

if __name__=='__main__':
    unittest.main()
