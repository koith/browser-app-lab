import hashlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from PIL import Image
from collect_yui_tagged_public_photographers import observed_photos, acquire

URL='https://pbs.twimg.com/media/ABCDEFGH.jpg?name=orig'
ACCOUNT='chinokun_photo'
PAGE='https://teapawt.net/'+ACCOUNT

def card(username, text, image=URL, extra=''):
    return '<div class="timeline-item" data-username="'+username+'">'+extra+\
           '<span>'+text+'</span><img data-original="'+image+'"></div>'

class PublicPhotographerTests(unittest.TestCase):
    def test_exact_tag_and_own_post_only(self):
        page=(card(ACCOUNT,'2026.11.07 심유이 @super_yuisan')+
              card('other_photographer','@super_yuisan')+
              card(ACCOUNT,'unrelated model')+
              card(ACCOUNT,'quoted',extra='<div class="quote">@super_yuisan</div>')+
              card(ACCOUNT,'@super_yuisan',extra='<div class="retweet-header">repost</div>'))
        found,link,cards=observed_photos(page,ACCOUNT,PAGE)
        self.assertEqual(found,[URL]);self.assertEqual(cards,1);self.assertIsNone(link)
        wrong,_,_=observed_photos(page,'Asura_Nii','https://teapawt.net/Asura_Nii')
        self.assertEqual(wrong,[])

    def test_physical_sha_and_exact_album_no_republish(self):
        b=io.BytesIO()
        Image.new('RGB',(900,1200),(51,91,132)).save(b,format='JPEG')
        raw=b.getvalue()
        sha=hashlib.sha256(raw).hexdigest()
        class Client:
            def get(self,url,**kwargs):
                assert url==PAGE
                text=card(ACCOUNT,'Model: 심유이 @super_yuisan')
                return type('Response',(),{'status_code':200,'url':url,
                    'headers':{'Content-Type':'text/html'},'text':text,
                    'content':text.encode('utf8')})()
        def download(url,source):
            assert url==URL and source['url']==PAGE
            return {'bytes':raw,'sha256':sha,'width':900,'height':1200,'extension':'jpg'},None
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);base=root/'apps/yui-gallery'
            base.mkdir(parents=True)
            (base/'owner-index.json').write_text(json.dumps({
                'model':'yui','albums':[{'id':'existing','images':[]}]}))
            (base/'stored-albums.json').write_text(json.dumps({
                'model':'yui','albums':[],'physical_verified_image_count':0}))
            one=acquire(root,accounts=[ACCOUNT],pages=1,client=Client(),download=download)
            self.assertEqual(one['new_sha'],1)
            saved=json.loads((base/'stored-albums.json').read_text())
            self.assertEqual(saved['physical_verified_image_count'],1)
            photo=saved['albums'][0]['images'][0]
            self.assertEqual(photo['sha256'],sha)
            self.assertEqual(hashlib.sha256((base/photo['url']).read_bytes()).hexdigest(),sha)
            twice=acquire(root,accounts=[ACCOUNT],pages=1,client=Client(),download=download)
            self.assertEqual(twice['new_sha'],0)
            self.assertEqual(len(json.loads((base/'stored-albums.json').read_text())['albums'][0]['images']),1)

if __name__=='__main__':unittest.main()
