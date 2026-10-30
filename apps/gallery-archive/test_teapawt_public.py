#!/usr/bin/env python3
"""Offline public feed cursor, author identity, byte-save regression."""
import hashlib
import io
import json
import tempfile
from pathlib import Path

from PIL import Image
from collect_teapawt_public import (
    capture, public_images_from_author, public_original_variant, safe_media_url)

SRC={"id":"yui-public-official-x-teapawt","title":"Yui photo feed",
     "account":"super_yuisan","kind":"teapawt","url":"https://teapawt.net/super_yuisan"}
P1='''<div class="timeline-item author-super_yuisan" data-username="super_yuisan">
<img data-src="https://pbs.twimg.com/media/FirstPhoto1234?format=jpg&amp;name=small"></div>
<div class="timeline-item author-otheruser retweet-super_yuisan" data-username="otheruser">
<img src="https://pbs.twimg.com/media/NotYuiPicture?format=jpg&amp;name=small"></div>
<a href="/super_yuisan?cursor=CURSOR123">Load more</a>'''
P2='''<div class="timeline-item author-super_yuisan" data-username="super_yuisan">
<a href="https://pbs.twimg.com/media/SecondPhoto1234?format=jpg&amp;name=large">Full image</a></div>'''

class Response:
    status_code=200
    headers={"Content-Type":"text/html;charset=utf-8"}
    def __init__(self,html,url):
        self.text,self.content,self.url=html,html.encode(),url

class Client:
    def get(self,url,**_):
        return Response(P2 if "cursor=" in url else P1,url)

def render_bytes(color):
    pic=Image.new("RGB",(480,720),color)
    out=io.BytesIO()
    pic.save(out,format="JPEG")
    return out.getvalue()

def main():
    urls,pagination,cards=public_images_from_author(P1,SRC,SRC["url"])
    assert cards==1 and len(urls)==1,urls
    assert "FirstPhoto1234" in urls[0] and "NotYuiPicture" not in str(urls)
    assert pagination.endswith("?cursor=CURSOR123"),pagination
    assert public_original_variant(urls[0])[0].endswith("name=orig")
    assert not safe_media_url("https://pbs.twimg.com.evil.test/media/Foo123456",SRC["url"])
    assert not safe_media_url("https://pbs.twimg.com/protected/privatephoto",SRC["url"])
    with tempfile.TemporaryDirectory() as tmp:
        payloads=[render_bytes("red"),render_bytes("blue")]
        def downloader(url,_):
            index=0 if "First" in url else 1
            raw=payloads[index]
            return {"bytes":raw,"sha256":hashlib.sha256(raw).hexdigest(),
                    "width":480,"height":720,"extension":"jpg"},None
        report=capture(SRC,Path(tmp),max_pages=4,workers=2,client=Client(),fetch=downloader)
        assert report["owner_authored_posts"]==2,report
        assert report["source_pages"]==2 and report["physical_decoded_files"]==2,report
        assert report["distinct_public_media_urls"]==2
        for digest in (hashlib.sha256(v).hexdigest() for v in payloads):
            photo=Path(tmp)/(digest+".jpg")
            assert photo.is_file()
            assert json.loads(photo.with_suffix(".json").read_text())["author"]["screen_name"]=="super_yuisan"
    print("TEAPAWT_PUBLIC_AUTHOR_CURSOR_TWO_REAL_FILES_PASS")

if __name__=="__main__":main()
