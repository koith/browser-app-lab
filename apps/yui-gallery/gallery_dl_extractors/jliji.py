"""Official gallery-dl external-extractor protocol for publicly visible Yui sets.

Read public server-rendered data-full addresses through TLS-verified HTTP,
then hand each unchanged network file back to gallery-dl.
No login, subscription access, or compressed output.
"""
from __future__ import annotations
import re
from html import unescape
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
    pattern=r"https?://(?:www\.)?jliji\.com/set/(\d+)(?:/?(?:\?.*)?)?$"
    example="https://www.jliji.com/set/12343"
    directory_fmt=("YUI","{album_id}")
    filename_fmt="{num:03}.{extension}"
    archive_fmt="{album_id}_{num}"

    def __init__(self,match):
        super().__init__(match)
        self.set_id=match.group(1)

    def items(self):
        origin=f"https://www.jliji.com/set/{self.set_id}"
        html=self.request(origin).text
        heading=re.search(r"<h1[^>]*>(.*?)</h1>", html, re.S)
        visible_title=unescape(re.sub(r"<[^>]+>", "", heading.group(1))).strip() if heading else ""
        if self.set_id in SETS:
            album_id,title,gallery_id,expected=SETS[self.set_id]
        else:
            if "Yui (유이)" not in visible_title:
                raise ValueError("Not the requested Korean Yui; refuse ambiguous model")
            count=re.search(r"(\d+)P\b", visible_title)
            if not count:
                raise ValueError("Public page has no declared image count")
            expected=int(count.group(1))
            album_id,title,gallery_id=f"jliji-{self.set_id}",visible_title,None
        selected={}
        groups={}
        for url in re.findall(r'data-full=["\x27]([^"\x27]+)',html):
            url=unescape(url)
            match=re.fullmatch(r"https://cdn\.jliji\.com/galleries/buondua/(\d+)/(\d+)\.(jpe?g|png|webp)",url,re.I)
            if match:
                gid,num,_=match.groups()
                groups.setdefault(int(gid),{})[int(num)]=url
        if gallery_id is not None:
            selected=groups.get(gallery_id,{})
        elif len(groups)==1:
            selected=next(iter(groups.values()))
        if set(selected)!=set(range(1,expected+1)):
            raise ValueError(f"Incomplete publicly visible set {album_id}: {len(selected)}/{expected}")
        common={"album_id":album_id,"title":title,"set_id":self.set_id,"expected":expected}
        yield Message.Directory,None,common
        for num,url in sorted(selected.items()):
            extension=url.rsplit(".",1)[-1].split("?",1)[0].lower()
            yield Message.Url,url,{**common,"num":num,"extension":extension,"source_page":origin}
