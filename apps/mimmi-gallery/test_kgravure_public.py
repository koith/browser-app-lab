#!/usr/bin/env python3
from bs4 import BeautifulSoup
from unittest.mock import patch
import collect_kgravure_public as m
class Response:
    def __init__(self,text,url):
        self.content=text.encode();self.url=url
    def raise_for_status(self):pass
def main():
    assert m.in_site("https://kgravure.vip/en/models/mimmi/")
    assert not m.in_site("https://kgravure.vip.evil.net/en/models/mimmi/")
    assert m.public_image("https://static.kgravure.vip/images/mimmi/001.webp")
    assert not m.public_image("https://another.site/images/mimmi.jpg")
    with patch.object(m.S,"get",return_value=Response('<main><a href="/en/models/mimmi/">Mimmi (42)</a><a href="/en/models/maruemon/">Maruemon</a></main>',m.INDEX)):
        found=m.profiles()
        assert found==["https://kgravure.vip/en/models/mimmi/"],found
    s=BeautifulSoup('<main><img data-src="https://static.kgravure.vip/sets/mimmi/001.jpg"/><a href="//cdn.kgravure.vip/sets/mimmi/002.webp">view</a><img src="https://evil.site/cover.jpg"/></main>',"html.parser")
    a=m.image_urls(s,"https://kgravure.vip/en/sets/test/")
    assert len(a)==2,a
    print("MIMMI_KGRAVURE_PUBLIC_SCOPE_AND_IMAGE_CANDIDATE_PASS")
if __name__=="__main__":main()
