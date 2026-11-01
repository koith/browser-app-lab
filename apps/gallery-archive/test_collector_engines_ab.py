#!/usr/bin/env python3
"""Offline comparison invariants for public engines; no live network."""
from io import BytesIO
from PIL import Image,ImageDraw
from collector_engines_ab import scoped_generic_html,safe_photo,verify_public
from direct_photo_pipeline import page_images


def test():
    page='https://djawaphoto.com/portfolio/nikke-privaty-sharp-lesson/'
    body=b'''<html><head><title>Nikke Yui photo album</title></head>
    <body class="sidebar-right"><article><div class="portfolio-content">
    <img src="https://djawaphoto.com/wp-content/uploads/2026/09/photo001.jpg">
    <div class="related"><img src="https://djawaphoto.com/wp-content/uploads/2026/09/other.jpg"></div>
    <img data-src="https://djawaphoto.com/wp-content/uploads/2026/09/photo002.jpg">
    <a href="https://djawaphoto.com/wp-content/uploads/2026/09/photo003.jpg"><img src="ignore.png"></a>
    </div></article></body></html>'''
    urls,status=scoped_generic_html(body,page,'yui')
    assert status=='scrapy_article_selector',status
    assert len(urls)==3,urls
    assert not any('other.jpg' in x for x in urls),urls
    assert not any('ignore.png' in x for x in urls),urls
    cross,status=scoped_generic_html(body,page,'mimmi')
    assert not cross and status=='no_model_heading'
    assert safe_photo('https://djawaphoto.com/wp-content/uploads/2026/09/photo001.jpg')
    assert not safe_photo('https://evil.example/secret.jpg')
    assert not safe_photo('http://djawaphoto.com/wp-content/uploads/2026/09/photo001.jpg')
    im=Image.new('RGB',(400,600),'white');d=ImageDraw.Draw(im)
    d.rectangle((10,10,300,450),fill=(10,50,240))
    o=BytesIO();im.save(o,format='JPEG',quality=95)
    class R:
        status_code=200
        content=o.getvalue()
    class S:
        def get(self,url,**kwargs):return R()
    verified=verify_public(S(),'https://djawaphoto.com/wp-content/uploads/test.jpg')
    assert verified['status']=='decoded_sha' and verified['width']==400,verified
    # A gallery page in which both engines discover identical photos is NOT a gain.
    first,_,_=page_images(body,page,'yui')
    assert {u for u in first if safe_photo(u)}.issubset(set(urls)),(first,urls)
    print('COLLECTOR_ENGINES_AB_OFFLINE_PASS')


if __name__=='__main__':test()
