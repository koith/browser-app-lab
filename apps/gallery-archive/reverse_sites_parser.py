"""Parse ordinary public Yandex same-image Sites results.

These are discovery leads, not photo files or gallery entries.
"""
import json
from html.parser import HTMLParser
from html import unescape
from urllib.parse import urlsplit, parse_qsl, urlencode

class StateParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.items=[]
    def handle_starttag(self, tag, attrs):
        for key,value in attrs:
            if key=="data-state" and value and len(value)<2000000:
                try:
                    self.items.append(json.loads(unescape(value)))
                except (ValueError,TypeError):
                    pass

def sites_from_html(html, normalize):
    parsed=StateParser()
    parsed.feed(html[:4000000])
    rows,seen=[],set()
    for payload in parsed.items:
        state=payload.get("initialState") if isinstance(payload,dict) else None
        if not isinstance(state,dict):continue
        for field in ("cbirSites","cbirSitesList"):
            wrapper=state.get(field) or {}
            if not isinstance(wrapper,dict):continue
            for match in wrapper.get("sites",[]):
                if not isinstance(match,dict):continue
                url=normalize(match.get("url",""))
                if not url or url in seen:continue
                seen.add(url)
                original=match.get("originalImage") or {}
                if not isinstance(original,dict):original={}
                photo=original.get("url")
                rows.append({
                    "url":url,
                    "label":str(match.get("title") or match.get("description") or "")[:200],
                    "matched_image_url":photo if isinstance(photo,str)
                        and photo.startswith("https://") else None,
                    "matched_width":original.get("width"),
                    "matched_height":original.get("height"),
                    "source_engine":"yandex_sites",
                })
    return rows
