#!/usr/bin/env python3
"""Dry-run test: official preview discovery, URL allowlist, image inspection."""
from io import BytesIO
from PIL import Image
import collect_official_previews as c

def main():
    assert c.valid_official("https://djawaphoto.com/portfolio/mimmi/")
    assert not c.valid_official("https://other.example/photo.jpg")
    assert not c.valid_official("https://djawaphoto.com.evil.tld/photo.jpg")
    html="""<main>
    <a href="/portfolio/mimmi-summer/">View</a>
    <img src="https://djawaphoto.com/wp-content/uploads/2026/08/sample_cv.jpg"/>
    <img data-src="https://djawaphoto.com/wp-content/uploads/2026/08/sample_1.jpg"/>
    <img src="https://evil.example/private.jpg"/>
    </main>"""
    from bs4 import BeautifulSoup
    urls=c.image_candidates(BeautifulSoup(html,'html.parser'),c.CATEGORY)
    assert len(urls)==2,urls
    assert c.count_photo_text("This book consists of film works with total 75 extremely-high resolution (5000 x 5000) photos.")==75
    assert c.norm("Happy Mimmi!")=="happy-mimmi"
    data=BytesIO()
    Image.effect_noise((640,960),48).convert("RGB").save(data,"PNG")
    class FakeResponse:
        def __init__(self):self.url="https://djawaphoto.com/wp-content/uploads/2026/08/sample_cv.jpg"
        def raise_for_status(self):pass
        def iter_content(self,chunk_size=65536):yield data.getvalue()
    original=c.SESSION.get
    try:
        c.SESSION.get=lambda *args,**kwargs:FakeResponse()
        p=c.probe_image("https://djawaphoto.com/wp-content/uploads/2026/08/sample_cv.jpg")
    finally:
        c.SESSION.get=original
    assert p["width"]==640 and p["height"]==960 and p["sha256"]
    assert p["saved_to_private_cloud"] is False
    print("MIMMI_OFFICIAL_PREVIEW_EXTRACTOR_UNIT_QA_PASS")
if __name__=="__main__": main()
