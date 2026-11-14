#!/usr/bin/env python3
"""Offline source-name accumulation and publisher target regression."""
import hashlib
import json
import tempfile
from pathlib import Path
from source_name_ledger import LEDGER,observe,ingest_discovery,queries,key
from publisher_completion import TARGETS,evaluate

def main():
    db=json.loads(LEDGER.read_text(encoding="utf-8"))
    assert len(db["works"])>=8
    all_queries=queries(db,"mimmi","djawa-pop-kitty-party")
    assert any("Ceyatic" in q for q in all_queries)
    assert any("밈미" in q for q in all_queries)
    assert any("沈慧圣" in q for q in queries(db,"yui","yui-meow-public-samples"))
    assert not queries(db,"yui","unknown-work")
    n=len(db["works"]["mimmi:djawa-pop-kitty-party"])
    assert observe(db,"mimmi","djawa-pop-kitty-party","Mimmi Kitty Party",
                   "https://example.org/album/1","unverified",False)=="pending"
    assert len(db["works"]["mimmi:djawa-pop-kitty-party"])==n
    assert observe(db,"mimmi","djawa-pop-kitty-party","Mimmi Kitty Party",
                   "https://example.org/album/1","sha_overlap",True)=="added"
    assert observe(db,"mimmi","djawa-pop-kitty-party","mimmi  kitty party",
                   "https://other.example.org/","sha_overlap",True)=="existing"
    assert key("Ｐｏｐ Kitty Party")==key("Pop Kitty Party")
    reports={"leads":[{"model":"mimmi","title":"DJAWA Pop Kitty Party",
        "exact_stored_title_matches":[{"id":"djawa-pop-kitty-party"}],
        "sources":[{"url":"https://example.org/title","tier":"catalogue"}]},
        {"model":"yui","title":"Yui","exact_stored_title_matches":[{"id":"one"},{"id":"two"}],
        "sources":[{"url":"https://example.org/suspect"}]}]}
    result=ingest_discovery(db,reports)
    assert result["added"]==1 and result["skipped_ambiguous"]==1,result
    specifications=json.loads(TARGETS.read_text(encoding="utf-8"))["works"]
    assert {x["album_id"]:x["declared_photo_count"] for x in specifications}=={
        "djawa-pop-kitty-party":123,"djawa-nikke-yuni":213,
        "djawa-janus-scary-lantern-night":88}
    with tempfile.TemporaryDirectory() as temp:
        root=Path(temp)
        home=root/"apps/mimmi-gallery"
        photo=home/"stored-albums/work/1.jpg"
        photo.parent.mkdir(parents=True)
        raw=b"test physical bytes"
        photo.write_bytes(raw)
        digest=hashlib.sha256(raw).hexdigest()
        row={"sha256":digest,"url":"stored-albums/work/1.jpg","width":8640,
             "height":5760,"watermark_status":"verified_none"}
        (home/"stored-albums.json").write_text(json.dumps({"albums":[{"id":"work","images":[row]}]}))
        spec=dict(specifications[0],album_id="work",declared_photo_count=1)
        result=evaluate(root,spec)
        assert result["repo_sha_verified_photos"]==1
        assert result["checks"]["official_quantity_verified_with_real_unique_files"]
        assert not result["complete"] and not result["checks"]["official_package_size_verified"]
        photo.write_bytes(b"tampered")
        assert evaluate(root,spec)["repo_sha_verified_photos"]==0
    print("CUMULATIVE_SITE_ALIAS_AND_PUBLISHER_COMPLETION_TEST_PASS")

if __name__=="__main__":main()
