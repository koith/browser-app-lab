#!/usr/bin/env python3
"""Independent CreamSoda public gallery parser, model ID, page 2+ and photo origin."""
from collect_xiutu_public import safe_article,safe_page,safe_media,listing_links,article_media,previous_verified_photo

def main():
    root="https://www.xiutu.me/photo/123456"
    assert safe_article(root)
    assert not safe_article("https://evil-xiutu.me/photo/123456")
    assert not safe_article("https://www.xiutu.me/download/123456")
    assert safe_page(root,root)
    assert safe_page(root+"/2",root)
    assert safe_page(root+"/19",root)
    assert not safe_page("https://www.xiutu.me/photo/654321",root)
    assert safe_media("https://cdn.xiutu.me/uploads/public-photo-03.jpg")
    assert safe_media("https://img-jp-a.cdnimg.vip/uploads/real-public-mimmi-photo.jpg")
    assert not safe_media("https://img-jp-a.cdnimg.vip.evil.test/photo.jpg")
    assert not safe_media("https://cdn.xiutu.me.evil.com/uploads/f.jpg")
    assert not safe_media("https://cdn.xiutu.me/api/private/f.jpg")
    assert not safe_media("http://cdn.xiutu.me/uploads/a.jpg")
    cat='''<main>
        <article><h2><a href="/photo/123456">[CreamSoda] Mimmi (밈미) Vol 3 Mashu Mimmi 59P</a></h2></article>
        <article><h2><a href="/photo/654321">[CreamSoda] Bambi Vol 3 63P</a></h2></article>
        <article><h2><a href="https://evil-xiutu.me/photo/111111">Mimmi Secret</a></h2></article>
    </main>'''
    assert listing_links(cat,"https://www.xiutu.me/korea/creamsoda")==[root]
    html='''<html><h1>[CreamSoda] Mimmi (밈미) Mashu Mimmi (59P)</h1>
    <article class="entry-content">
      <img data-src="https://cdn.xiutu.me/uploads/img1.jpg" alt="Mimmi 001">
      <img src="https://cdn.xiutu.me/uploads/img2.jpg" alt="Mimmi 002">
      <img src="https://cdn.xiutu.me/uploads/logo.jpg" alt="logo"/>
    </article>
    <nav class="pagination"><a href="/photo/123456/2">2</a><a href="/photo/123456/3">3</a></nav></html>'''
    photos,pages,matched=article_media(html,root,root)
    assert matched and len(photos)==2,photos
    assert pages==[root+"/2",root+"/3"],pages
    assert article_media(html.replace("Mimmi","WrongModel").replace("밈미","다른모델"),root,root)[2] is False
    verified={"url":"https://cdn.xiutu.me/uploads/mimmi0001.jpg",
              "sha256":"f"*64,"bytes":10240,"width":640,"height":920}
    cached=None
    for day in ("2026-10-25","2026-10-26","2026-10-27","2026-10-28"):
        cached=previous_verified_photo(verified["url"],verified,day=day)
        if cached:break
    assert cached and cached["previously_verified_only"]
    assert previous_verified_photo(verified["url"],verified,refresh_every=1) is None
    assert previous_verified_photo("https://evil.com/photo.jpg",verified) is None
    print("MIMMI_XIUTU_2ND_SOURCE_ID_PAGINATION_AND_PUBLIC_IMAGE_TEST_PASS")

if __name__=="__main__":main()
