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
    seed={"url":"https://cdn.v2ph.com/photos/keep.jpg","sha256":"a"*64,"bytes":120000,
          "width":2000,"height":3000,"number":1}
    fresh={"url":"https://cdn.v2ph.com/photos/new.jpg","sha256":"b"*64,"bytes":160000,
           "width":2200,"height":3200,"number":1}
    invalid={"url":"https://evil.example/photo.jpg","sha256":"c"*64,"bytes":150000,
             "width":2300,"height":3200}
    # HTTP 429 or a completely blocked scan must not erase prior evidence.
    retained=m.preserve_verified_samples([], [seed,invalid], 100)
    assert len(retained)==1 and retained[0]["url"]==seed["url"]
    assert retained[0]["carried_from_previous_verification"] is True
    merged=m.preserve_verified_samples([fresh],[seed,fresh],100)
    assert [p["number"] for p in merged]==[1,2] and len(merged)==2
    assert merged[0]["url"]==fresh["url"] and merged[1]["url"]==seed["url"]
    assert "carried_from_previous_verification" not in merged[0]
    assert merged[1]["carried_from_previous_verification"] is True
    assert len(m.preserve_verified_samples([fresh],[seed],1))==1
    print("MIMMI_V2PH_PUBLIC_EXTRACTOR_QA_PASS")
if __name__=="__main__":main()
