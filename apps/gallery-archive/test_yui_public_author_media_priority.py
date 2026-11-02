#!/usr/bin/env python3
"""Public author-only feed should be visited before X's blocked statuses."""
import hashlib
import json
import tempfile
import unittest
from io import BytesIO
from pathlib import Path
from PIL import Image
from direct_photo_pipeline import collect,page_images,reviewed_direct_source,reviewed_direct_media

MEDIA='https://teapawt.net/super_yuisan/media'
URL='https://pbs.twimg.com/media/OwnerNewPublic12345.jpg?name=orig'
OTHER='https://pbs.twimg.com/media/OtherPersonBlocked.jpg?name=orig'
PUBLIC_HTML=f'''<main><div class="timeline-item" data-username="super_yuisan">
  <a href="/super_yuisan/status/2117242902825091424">Original X post</a>
  <a href="{URL}">Own original photo</a>
  <div class="quote"><img src="{OTHER}"></div>
</div><div class="timeline-item" data-username="someone_else">
  <img src="{OTHER}">
</div></main>'''


def image():
    photo=Image.new('RGB',(400,600))
    photo.putdata([((x*7+13)%256,(y*11+25)%256,((x+y)*19+5)%256)
                   for y in range(600) for x in range(400)])
    out=BytesIO()
    photo.save(out,format='JPEG',quality=92)
    return out.getvalue()


class Cases(unittest.TestCase):
    def test_exact_author_media_tab_parser_and_storage_rights_gate(self):
        self.assertTrue(reviewed_direct_source(MEDIA,'yui'))
        self.assertTrue(reviewed_direct_media(URL,MEDIA,'yui'))
        self.assertFalse(reviewed_direct_media(OTHER,'https://www.v2ph.com/a/','yui'))
        self.assertFalse(reviewed_direct_source(MEDIA,'mimmi'))
        urls,pages,status=page_images(PUBLIC_HTML.encode(),MEDIA,'yui')
        self.assertEqual(status,'scoped_public_page')
        self.assertEqual(urls,[URL],urls)

    def test_model_author_media_precedes_many_blocked_x_pages(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)
            base=root/'apps/yui-gallery'
            base.mkdir(parents=True)
            (base/'stored-albums.json').write_text('{"albums":[]}')
            x_pages=['https://x.com/super_yuisan/status/'+str(2116000000000000000+i)
                      for i in range(90)]
            (base/'public-work-pages.json').write_text(json.dumps({'albums':[{
                'id':'public-yui-sns','title':'Yui Sim own public media',
                'source':'https://teapawt.net/super_yuisan',
                'source_pages':[MEDIA,*x_pages]}]}))
            old_image=image()
            fresh_bytes=image()
            # Force existing owner's SHA to differ from the new photo.
            owner={'model':'yui','schema_version':1,'albums':[
                {'id':'public-yui-sns','images':[{
                    'number':1,'sha256':'0'*64}]}]}
            class Client:
                blocked_origins=set()
                def __init__(self):self.calls=[]
                def get(self,url):
                    self.calls.append(url)
                    if url==MEDIA:return type('R',(),{'content':PUBLIC_HTML.encode()})()
                    if url==URL:return type('R',(),{'content':fresh_bytes})()
                    raise AssertionError('Blocked X page requested instead of public author media')
            client=Client()
            result=collect(root,'yui',owner,root/'stage',3,1,client,
                           page_cycle=999,reviewed_source_only=True)
            self.assertEqual(result['new_local_individual_files'],1,result)
            self.assertEqual(client.calls,[MEDIA,URL],client.calls)
            row=json.loads((root/'stage/metadata/catalog.json').read_text())['albums'][0]['images'][0]
            self.assertEqual(row['number'],2)
            self.assertEqual(row['sha256'],hashlib.sha256(fresh_bytes).hexdigest())
            self.assertEqual((root/'stage'/row['key']).read_bytes(),fresh_bytes)


if __name__=='__main__':
    unittest.main(verbosity=2)
