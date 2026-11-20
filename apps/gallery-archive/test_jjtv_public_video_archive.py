#!/usr/bin/env python3
import unittest
import hashlib
from io import BytesIO
from PIL import Image
from tempfile import TemporaryDirectory
from pathlib import Path
import json
import sys
sys.path.insert(0,str(Path(__file__).parent))
from jjtv_public_video_archive import (actual_article,inspect_mp4,links_from_search,
                                       crawl,SiteError,same_public_host)

class FakeClient:
    def __init__(self,pages):self.pages=pages
    def get(self,url,max_bytes=1800000,kind="html"):
        if url not in self.pages:raise SiteError("http_403")
        return self.pages[url]

class Tests(unittest.TestCase):
    def test_safe_hosts(self):
        self.assertTrue(same_public_host("https://jjtv.kr/15/154066"))
        self.assertFalse(same_public_host("http://jjtv.kr/15/154066"))
        self.assertFalse(same_public_host("https://jjtv.kr.evil.test/15/1"))
    def test_page_identity_in_heading_not_sidebar(self):
        raw=b'<html><title>Somebody else</title><main><a href="/15/1">Yui</a></main></html>'
        entry,state=actual_article(raw,"https://jjtv.kr/15/100","yui")
        self.assertIsNone(entry)
        self.assertEqual(state,"model_not_in_article_heading")
    def test_video_urls_only_from_matching_article(self):
        raw=('''<html><title>심유이 — video</title><article><video><source src=
        "https://img2.jjtv.kr/public_01.mp4"></video></article>
        <aside><video src="https://img2.jjtv.kr/unrelated.mp4"></video></aside></html>''').encode()
        proof,state=actual_article(raw,"https://jjtv.kr/15/154066","yui")
        self.assertEqual(state,"ok")
        self.assertEqual(proof["videos"],["https://img2.jjtv.kr/public_01.mp4"])
    def test_search_matches_model_title_only(self):
        raw='''<a href="/15/154066">심유이 메이드</a><a href="/15/4">미미 다른 사람</a>
        <a href="https://evil.test/15/7">심유이</a>'''.encode()
        self.assertEqual(links_from_search(raw,"yui"),["https://jjtv.kr/15/154066"])
    def test_real_video_bytes_only(self):
        with self.assertRaises(SiteError):inspect_mp4(b"hello")
        self.assertEqual(len(inspect_mp4(b"\0\0\0\x18ftyp"+bytes(1100))),64)
    def test_blocked_site_does_not_claim_archived_video(self):
        with TemporaryDirectory() as d:
            base=Path(d)/"apps/yui-gallery"
            base.mkdir(parents=True)
            (base/"videos.json").write_text(json.dumps({"model":"yui","videos":[]}))
            x=crawl("yui",root=d,client=FakeClient({}),max_pages=1,max_posts=3,archive=True,delay=0)
            self.assertEqual(x["archived_files"],0)
            self.assertGreater(sum(x["errors"].values()),0)

    def test_article_photo_scope_excludes_video_poster_and_sidebar(self):
        page=("https://jjtv.kr/15/154066")
        html=('''<html><title>심유이 새 화보 사진</title><article>
            <video poster="https://img2.jjtv.kr/video_0000.jpg"></video>
            <img src="https://img2.jjtv.kr/video_0000.jpg">
            <img data-original="https://img2.jjtv.kr/yui-cut-01.jpg">
            </article><aside><img src="https://img2.jjtv.kr/unrelated.jpg"></aside></html>''').encode()
        item,state=actual_article(html,page,"yui")
        self.assertEqual(state,"ok")
        self.assertEqual(item["photos"],["https://img2.jjtv.kr/yui-cut-01.jpg"])

    def test_genuine_article_photo_is_staged_with_sha_and_publisher_provenance(self):
        page="https://jjtv.kr/15/154066"
        image_url="https://img2.jjtv.kr/yui-cut-01.jpg"
        html=('''<html><title>심유이 공개 촬영 사진</title>
                <article><h1>심유이 공개 촬영 사진</h1>
                <img data-original="https://img2.jjtv.kr/yui-cut-01.jpg">
                </article></html>''').encode()
        image=Image.effect_noise((950,1150),85).convert("RGB")
        out=BytesIO()
        image.save(out,"JPEG",quality=86)
        with TemporaryDirectory() as d:
            base=Path(d)/"apps/yui-gallery"
            base.mkdir(parents=True)
            (base/"videos.json").write_text(json.dumps({"model":"yui","videos":[]}))
            stage=Path(d)/"jjtv-stage"
            result=crawl("yui",root=d,client=FakeClient({
                page:html,image_url:out.getvalue()
            }),max_pages=1,max_posts=2,archive=True,stage=stage,delay=0)
            self.assertEqual(result["staged_photo_sha_not_published"],1)
            self.assertEqual(result["archived_files"],0)
            stored=json.loads((stage/"metadata/catalog.json").read_text())
            self.assertEqual(stored["model"],"yui")
            self.assertEqual(stored["verified_new_work_sources"][0]["source"],page)
            self.assertEqual(stored["verified_new_work_sources"][0]["proof"],
                "unique_named_work_page_model_and_edition")
            photo=stored["albums"][0]["images"][0]
            self.assertEqual(photo["sha256"],hashlib.sha256(out.getvalue()).hexdigest())
            self.assertEqual((stage/photo["key"]).read_bytes(),out.getvalue())

if __name__=="__main__":unittest.main(verbosity=2)
