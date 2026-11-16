#!/usr/bin/env python3
"""Offline regression: image-first search prioritization and Yandex JSON."""
import html
import json
import tempfile
from pathlib import Path

from reverse_seed_priority import seeds
from reverse_sites_parser import sites_from_html
from reverse_image_sweep import search_one,sweep,query_page,diversified_seed_window
from reverse_image_discovery import untrack

def fixture(base):
    for model in ("mimmi","yui"):
        p=base/(model+"-gallery")
        p.mkdir()
        (p/"stored-albums.json").write_text(json.dumps({"model":model,"albums":[]}))
        albums=[]
        for aid,count in (("one",3),("full",75)):
            photos=[{"number":n+1,"sha256":f"{(n+1)%10}"*64,
                     "bytes":150000,"preview_sha256":"b"*64}
                    for n in range(count)]
            albums.append({"id":aid,"title":("Mimmi" if model=="mimmi" else "Yui")+" Red Shirt",
                           "images":photos})
        (p/"owner-index.json").write_text(json.dumps({
            "schema_version":1,"storage":"sha-verified-owner-metadata-only",
            "model":model,"albums":albums}))

class FakeResponse:
    status_code=200
    headers={"Content-Type":"text/html"}
    def __init__(self,text):
        self.text=text
        self.content=text.encode()

class FakeClient:
    def get(self,url,params=None,**kw):
        assert kw.get("allow_redirects") is False
        record={"initialState":{"cbirSites":{"sites":[{
            "url":"https://www.v2ph.com/album/some.html?utm_source=yandexsmartcamera",
            "title":"DJAWA Mimmi Red Shirt",
            "originalImage":{"url":"https://cdn.v2ph.com/photos/frame.jpg",
                             "width":2200,"height":3300}
        }]}}}
        text='<div data-state="'+html.escape(json.dumps(record))+'"></div>'
        return FakeResponse(text)

def main():
    class RedirectClient:
        def __init__(self,location):self.location=location;self.calls=0
        def get(self,url,**kw):
            self.calls+=1
            if self.calls==1:
                r=FakeResponse('');r.status_code=302;r.headers={'Location':self.location};return r
            return FakeResponse('<html>normal search results</html>')
    normal=RedirectClient('/images/search?q=public')
    assert query_page(normal,'https://www.bing.com/images/search',{})[0]=='ok'
    assert normal.calls==2
    for location in ['https://other.example/result','/captcha/verify','/login',
                     'https://www.bing.com:badport/images/search']:
        boundary=RedirectClient(location)
        assert query_page(boundary,'https://www.bing.com/images/search',{})[0]=='redirect_access_boundary_not_followed'
        assert boundary.calls==1
    with tempfile.TemporaryDirectory() as tmp:
        base=Path(tmp)
        fixture(base)
        entries=seeds(base)
        assert len(entries)==12,len(entries)
        assert entries[0]["owner_saved_count"]==3,entries
        large=[x for x in entries if x["album_id"]=="full"]
        assert large and all(x["owner_saved_count"]==10 for x in large),large
        assert all(x["owner_slot_count"]==75 for x in large),large
        assert entries[0]["seed_kind"]=="public-gateway-cover"
        assert all("cookie" not in s["public_image_url"] for s in entries)
        matches=sites_from_html(FakeClient().get("",{},allow_redirects=False).text,untrack)
        assert len(matches)==1,matches
        assert matches[0]["matched_width"]==2200,matches
        accepted=search_one(entries[0],FakeClient())
        if entries[0]["model"]=="mimmi":
            assert len(accepted["candidate_pages"])==1,accepted
        # The real all-cut source queue used to scan 8 frames from just
        # two albums. Distinct-album coverage must equal the number of
        # different works up to the limit, without any extra network calls.
        complete=seeds(base,all_cuts=True)
        for offset in (0,1,5,17,47):
            selected=diversified_seed_window(complete,8,offset)
            assert len(selected)==8,(offset,len(selected))
            assert len({(x['model'],x['album_id'],x['photo_sha256']) for x in selected})==8,selected
        # With an offset incremented by 8 per scheduled run, every immutable
        # photo must be reached before any photo is revisited.
        key=lambda p:(p['model'],p['album_id'],p['photo_sha256'])
        census={key(p) for p in complete}
        visited=set()
        for run in range((len(census)+7)//8):
            batch=diversified_seed_window(complete,8,run*8)
            remaining=len(census)-len(visited)
            # Final batch may wrap only AFTER the remaining new SHA cuts.
            assert not visited.intersection(map(key,batch[:remaining])),(run,batch)
            visited.update(map(key,batch))
        assert visited==census,(len(visited),len(census))
        assert len({(x['model'],x['album_id']) for x in diversified_seed_window(complete,8,0)})==4
        # Regression: the old epoch=offset//album_count skipped half of a
        # ten-photo single-album archive (offset 0,8,16,...).
        single=[{'model':'mimmi','album_id':'only','photo_sha256':f'{i:064x}'}
                for i in range(10)]
        reached={key(p) for run in range(2)
                 for p in diversified_seed_window(single,8,run*8)}
        assert len(reached)==10,reached
        first=diversified_seed_window(complete,4,0)
        rotated=diversified_seed_window(complete,4,4)
        assert {x['photo_sha256'] for x in first}!={x['photo_sha256'] for x in rotated}
        long_scan=sweep(base,8,0,workers=2,client_factory=FakeClient,all_cuts=True)
        assert long_scan['unique_albums_queried']==4,long_scan
        assert long_scan['seed_queries']==8,long_scan
        assert long_scan['physical_photos_new']==0,long_scan
        scan=sweep(base,4,0,workers=2,client_factory=FakeClient)
        assert scan["seed_queries"]==4,scan
        assert scan["unique_albums_queried"]==4,scan
        assert scan["gallery_photos_new"]==0,scan
        assert scan["physical_photos_new"]==0,scan
        assert scan["research_only"],scan
    # An unrelated Yandex image-result page must not suppress Bing's
    # independent model-matched result. This was the live zero-yield bug.
    class UnrelatedFirstEngine:
        def get(self,url,params=None,**kw):
            if "yandex.com" in url:
                return FakeResponse('<a href="https://www.v2ph.com/album/other-coser.html">Other model only</a>')
            assert "bing.com" in url, url
            return FakeResponse('<a href="https://www.v2ph.com/album/mimmi-red-shirt.html">DJAWA Mimmi Red Shirt</a>')
    seed={"model":"mimmi","album_id":"djawa-red-shirt",
          "album_title":"Mimmi Red Shirt","photo_sha256":"a"*64,
          "public_image_url":"https://example.org/public.jpg","owner_saved_count":3}
    recovered=search_one(seed,UnrelatedFirstEngine())
    assert recovered["matched_urls_by_engine"]["yandex_sites"]==0,recovered
    assert recovered["matched_urls_by_engine"]["bing"]==1,recovered
    assert recovered["off_model_rejected"]>=1,recovered
    assert len(recovered["candidate_pages"])==1,recovered
    assert recovered["candidate_pages"][0]["url"].endswith("mimmi-red-shirt.html"),recovered
    assert recovered["originals_stored"]==recovered["visible_gallery_added"]==0
    print("IMAGE_FIRST_AGGRESSIVE_SOURCE_FIXTURE_PASS")

if __name__=="__main__":
    main()
