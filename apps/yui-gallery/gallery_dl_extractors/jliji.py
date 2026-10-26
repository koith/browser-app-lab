"""Official gallery-dl external-extractor protocol for publicly visible Yui sets.

This adapter uses a real Chromium page for lazy-loaded photo addresses,
then hands each individual, original network file back to gallery-dl.
No login, subscription access, or compressed output.
"""
from __future__ import annotations
import re
from gallery_dl.extractor.common import Extractor, Message

SETS={
    "12343":("yuis-present33","SWEETBOX — Yui's Present",54756,33),
    "14973":("athletic-club104","Yui — Athletic Club",56008,104),
    "14346":("wet-yui80","Yui — Wet Yui",42862,80),
    "19356":("teddy-bear97","SWEETBOX — Teddy Bear",49348,97),
}

class JlijiYuiSetExtractor(Extractor):
    category="yui_jliji"
    subcategory="set"
    pattern=r"https?://(?:www\.)?jliji\.com/set/(12343|14973|14346|19356)(?:/?(?:\?.*)?)?$"
    example="https://www.jliji.com/set/12343"
    directory_fmt=("YUI","{album_id}")
    filename_fmt="{num:03}.{extension}"
    archive_fmt="{album_id}_{num}"

    def __init__(self,match):
        super().__init__(match)
        self.set_id=match.group(1)

    def items(self):
        from playwright.sync_api import sync_playwright
        album_id,title,gallery_id,expected=SETS[self.set_id]
        origin=f"https://www.jliji.com/set/{self.set_id}"
        prefix=f"https://cdn.jliji.com/galleries/buondua/{gallery_id}/"
        selected={}
        with sync_playwright() as playwright:
            browser=playwright.chromium.launch(headless=True)
            try:
                page=browser.new_page(viewport={"width":1280,"height":900})
                page.goto(origin,wait_until="domcontentloaded",timeout=35000)
                page.wait_for_timeout(600)
                for _ in range(28):
                    page.evaluate("window.scrollBy(0, Math.max(650, innerHeight*0.92))")
                    page.wait_for_timeout(120)
                urls=page.locator("img[data-full]").evaluate_all(
                    "(imgs)=>imgs.map(im=>im.getAttribute('data-full')).filter(Boolean)")
                for url in urls:
                    if not url.startswith(prefix):
                        continue
                    match=re.search(r"/(\d+)\.(jpe?g|png|webp)(?:\?.*)?$",url,re.I)
                    if match:
                        selected[int(match.group(1))]=url
            finally:
                browser.close()
        if set(selected)!=set(range(1,expected+1)):
            raise ValueError(f"Incomplete publicly visible set {album_id}: {len(selected)}/{expected}")
        common={"album_id":album_id,"title":title,"set_id":self.set_id}
        yield Message.Directory,common
        for num,url in sorted(selected.items()):
            extension=url.rsplit(".",1)[-1].split("?",1)[0].lower()
            yield Message.Url,url,{**common,"num":num,"extension":extension,"source_page":origin}
