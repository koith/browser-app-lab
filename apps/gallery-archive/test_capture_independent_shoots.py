#!/usr/bin/env python3
"""Offline owner-private shoot archive tests; refuse unrelated cosplayers/URLs."""
import hashlib
import io
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from zipfile import ZipFile
from PIL import Image
from capture_independent_shoots import archive,source_images,allowed_image,source_photo_pages

def make_jpg(color):
    im=Image.new("RGB",(640,820),color)
    b=io.BytesIO()
    im.save(b,"JPEG",quality=85)
    return b.getvalue()

class FakeResult:
    def __init__(self,url,html=None,data=None):
        self.url=url
        self.text=html
        self.data=data
    def raise_for_status(self):pass
    def iter_content(self,chunk_size=1024):yield self.data
    def close(self):pass
class Fake:
    def __init__(self,pages,images):
        self.pages=pages
        self.images=images
    def get(self,url,**kwargs):
        if url in self.pages:return FakeResult(url,html=self.pages[url])
        # All synthetic photos use same supported public image endpoint
        urlbase=url.split("?")[0]
        if urlbase in self.images:return FakeResult(url,data=self.images[urlbase])
        raise ValueError("Fake source not present")

def main():
    yui_photo="https://pbs.twimg.com/media/YuiPhoto.jpg"
    wrong_photo="https://pbs.twimg.com/media/OtherPerson.jpg"
    yui_src={"id":"yui-photographer-test","title":"Yui official photo",
             "kind":"teapawt-tagged","url":"https://teapawt.net/cos_swee",
             "author":"cos_swee","required_mention":"@super_yuisan","photo_host":"pbs.twimg.com"}
    html="""<html><div class="timeline-item" data-username="cos_swee">
      <div class="tweet-content">NIKKE model @super_yuisan · photo</div>
      <div class="attachments"><a class="still-image" href="%s">photo</a></div></div>
      <div class="timeline-item" data-username="someone_else"><div class="tweet-content">
      unrelated cosplay model @different_user</div><div class="attachments">
      <a class="still-image" href="%s">another model</a></div></div></html>"""%(yui_photo,wrong_photo)
    assert source_images(yui_src,html)==[yui_photo]
    assert not allowed_image("https://evil.example/unsafe.jpg",yui_src)
    assert source_images(yui_src,html.replace("@super_yuisan","@not_yui"))==[]
    # A photographer's second/third public page must be visited and only
    # specifically model-tagged photos from those pages may enter the archive.
    page2_url=yui_src["url"]+"?cursor=second"
    later_image="https://pbs.twimg.com/media/YuiPhotographerSecond.jpg"
    first_page=html.replace("</html>",'<a href="?cursor=second">Load more</a></html>')
    later_page=html.replace(yui_photo,later_image)
    paginated=Fake({yui_src["url"]:first_page,page2_url:later_page},{})
    yui_src["max_pages"]=5
    links,pages,errors=source_photo_pages(paginated,yui_src)
    assert pages==2 and links==[yui_photo,later_image] and not errors,(links,pages,errors)
    yui_src["max_pages"]=1
    limited_links,limited_pages,_=source_photo_pages(paginated,yui_src)
    assert limited_pages==1 and limited_links==[yui_photo]
    mimmi_url="https://upload2.inven.co.kr/upload/2019/11/20/bbs/test.jpg?MW=800"
    mimmi_src={"id":"mimmi-test-sana","title":"SANA independent",
         "kind":"inven-article","url":"https://www.inven.co.kr/board/webzine/2898/1741",
         "photo_host":"upload2.inven.co.kr",
         "direct_public_images":[mimmi_url]}
    article="<html>모델 : 밈미님 촬영 : SANA님 소녀전선 M4 SOPMOD II</html>"
    assert source_images(mimmi_src,article)==[mimmi_url]
    assert source_images(mimmi_src,"Other cosplayer's page")==[]
    twoucan_src={"id":"mimmi-official-test","title":"Mimmi official",
                 "kind":"twoucan-author","url":"https://twoucan.com/profile/Mimmi_official",
                 "photo_host":"pbs.twimg.com","required_mention":"@Mimmi_official"}
    assert source_images(twoucan_src,"<html>@Mimmi_official <a href='"+yui_photo+"'>photo</a></html>")==[yui_photo]
    yui_raw=make_jpg((70,110,190));mimmi_raw=make_jpg((190,120,110))
    with TemporaryDirectory() as folder:
        base=Path(folder)
        yui_sources={"yui":{"source_jobs":[yui_src]}}
        yui_catalog={"model":"yui","schema_version":1,"albums":[]}
        fake=Fake({yui_src["url"]:html},{yui_photo:yui_raw,wrong_photo:make_jpg((100,90,90))})
        n=archive("yui",yui_sources,yui_catalog,fake,base/"yui")
        assert n==1,n
        with ZipFile(base/"yui/yui-indie-private-import.zip") as z:
            m=json.loads(z.read("manifest.json"))
            assert m["physical_verified_image_count"]==1
            assert m["albums"][0]["id"]=="yui-photographer-test"
            record=m["albums"][0]["images"][0]
            assert record["number"]==1
            assert z.read(record["url"])==yui_raw
            # No unrelated person's media bytes should exist in this ZIP.
            assert len(z.namelist())==2
        yui_catalog["albums"]=m["albums"]
        no_new=archive("yui",yui_sources,yui_catalog,fake,base/"yui-repeat")
        assert no_new==0 and not list((base/"yui-repeat").glob("*private-import.zip"))
        mimmi_src["direct_public_images"]=[mimmi_url]
        mimmi_sources={"mimmi":{"source_jobs":[mimmi_src]}}
        mimmi_fake=Fake({mimmi_src["url"]:article},{mimmi_url.split("?")[0]:mimmi_raw})
        n=archive("mimmi",mimmi_sources,{"schema_version":1,"model":"mimmi","albums":[]},
                  mimmi_fake,base/"mimmi")
        assert n==1
        with ZipFile(base/"mimmi/mimmi-indie-private-import.zip") as z:
            m=json.loads(z.read("manifest.json"))
            assert z.read(m["albums"][0]["images"][0]["url"])==mimmi_raw
        print("INDEPENDENT_SHOOT_REAL_PHOTO_SHA_AND_IDENTITY_TEST_PASS",flush=True)

if __name__=="__main__":main()
