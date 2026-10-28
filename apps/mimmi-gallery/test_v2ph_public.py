#!/usr/bin/env python3
from bs4 import BeautifulSoup
import collect_v2ph_public as m

def main():
    assert m.safe_photo("https://cdn.v2ph.com/photos/abc.jpg")
    assert not m.safe_photo("https://cdn.v2ph.com.evil.com/photos/abc.jpg")
    assert not m.safe_photo("https://cdn.v2ph.com/login/abc.jpg")
    assert m.safe_source("https://www.v2ph.com/album/axm7n43z.html")
    assert not m.safe_source("https://evil.com/album/axm7n43z.html")
    html="""<h1>[DJAWA] Mimmi</h1>
      <div class="album_photo"><a href="https://cdn.v2ph.com/photos/X1.jpg"><img data-src="https://cdn.v2ph.com/photos/X1.jpg"></a></div>
      <img src="//cdn.v2ph.com/photos/X2.webp"/>
      <img src="https://example.com/photos/Z3.jpg"/>
      <img src="/login/auth.jpg"/>"""
    photos=m.photos_on_page(BeautifulSoup(html,"html.parser"),"https://www.v2ph.com/album/a.html")
    assert photos==["https://cdn.v2ph.com/photos/X1.jpg","https://cdn.v2ph.com/photos/X2.webp"],photos
    print("MIMMI_V2PH_PUBLIC_EXTRACTOR_QA_PASS")
if __name__=="__main__":main()
