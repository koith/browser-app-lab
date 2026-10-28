#!/usr/bin/env python3
from collect_pixibb_public import safe_page,safe_photo,page_photos,verified_history,SOURCE
def main():
    root=SOURCE[0]["source"]
    assert safe_page(root,root)
    assert safe_page(root+"18/",root)
    assert not safe_page(root+"19/login/",root)
    assert not safe_page("https://cosplay.pixibb.com/wp-admin/",root)
    assert not safe_page("https://evil.test"+root.split(".com")[-1],root)
    assert safe_photo("https://imgx001.pixibb.com/photo/abc.jpg")
    assert safe_photo("https://cosplay.pixibb.com/wp-content/uploads/2025/01/a.webp")
    assert not safe_photo("http://imgx001.pixibb.com/abc.jpg")
    assert not safe_photo("https://evil.pixibb.com/image.jpg")
    assert not safe_photo("https://cosplay.pixibb.com/download/photo.jpg")
    html='''<title>DJAWA Photo Mimmi - Nikke Alice</title><main><h1>Mimmi Nikke Alice</h1>
    <img src="https://imgx001.pixibb.com/photos/abc.jpg" alt="Mimmi Alice 001">
    <img data-lazy-src="https://imgx001.pixibb.com/photos/def.jpg" alt="Mimmi Alice 002">
    <a href="https://imgx001.pixibb.com/photos/ghi.jpg"><img src="/wp-content/uploads/2025/01/thumb.webp"></a>
    <img src="https://evil.test/a.jpg"></main>'''
    urls,matched=page_photos(html,root)
    assert matched and len(urls)==4,urls
    assert urls[0].endswith("abc.jpg") and urls[1].endswith("def.jpg")
    bad,m=page_photos(html.replace("Mimmi","SomeoneElse"),root)
    assert not m and not bad
    sample={"sha256":"a"*64,"bytes":10000,"width":1200,"height":800,
        "url":"https://imgx001.pixibb.com/photos/a.jpg"}
    assert len(verified_history([sample,sample],200))==1
    assert verified_history([{**sample,"sha256":"INVALID"}],200)==[]
    from collect_pixibb_public import all_sources
    works=all_sources()
    assert len(works)>=10,len(works)
    assert len({w["source"].rstrip("/") for w in works})==len(works)
    assert any("witchs-witchcraft" in w["source"] for w in works)
    assert any("cyberpunk-girl" in w["source"] for w in works)
    assert any("kitsune-miko-a-ver" in w["source"] for w in works)
    print("MIMMI_PIXIBB_PAGINATION_LAZY_SRC_AND_SHA_TEST_PASS")

if __name__=="__main__":main()
