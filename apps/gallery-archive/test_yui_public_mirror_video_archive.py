#!/usr/bin/env python3
import hashlib
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import sys
import unittest
sys.path.insert(0,str(Path(__file__).parent))
from yui_public_mirror_video_archive import (MediaError,is_observed_public_video,
                                              archive,ARTICLE)

URL="https://manpeace.org/data/video/202512/apdlemqhrtladbdl (1).mp4"

class Fake:
    def __init__(self,bytes=None):self.bytes=bytes;self.calls=[]
    def get(self,url,cap):
        self.calls.append(url)
        if self.bytes is None:raise MediaError("robots_or_public_host_denied")
        return self.bytes

class Tests(unittest.TestCase):
    def setup(self,root,kind="remote_mp4"):
        base=Path(root)/"apps/yui-gallery"
        base.mkdir(parents=True)
        cat={"schema_version":1,"model":"yui","videos":[{
          "id":"yui-maid-mirror-public-1","title":"Yui",
          "kind":kind,"media_url":URL,"source_url":ARTICLE}]}
        (base/"videos.json").write_text(json.dumps(cat))
        return base
    def test_only_precise_public_source_allowed(self):
        self.assertTrue(is_observed_public_video(URL))
        for value in ("http://manpeace.org/data/video/202512/a.mp4",
                      "https://manpeace.org.evil.net/data/video/202512/a.mp4",
                      "https://manpeace.org/private.mp4",
                      "https://user:password@manpeace.org/data/video/202512/a.mp4"):
            self.assertFalse(is_observed_public_video(value))
    def test_duplicate_wildcard_robots_disallow_is_strictly_honored(self):
        class Session:
            def __init__(self):
                self.headers={}
            def get(self,*args,**kwargs):
                class Response:
                    status_code=200
                    text="User-agent: *\\nAllow: /\\nUser-agent: *\\nDisallow: /data/\\n"
                    content=text.encode("utf-8")
                return Response()
        from yui_public_mirror_video_archive import PublicMediaClient
        client=PublicMediaClient(session=Session())
        self.assertFalse(client.permitted(URL))

    def test_verified_real_mp4_stored_and_catalog_immutable_sha(self):
        raw=b"\0\0\0\x18ftyp"+bytes(5500)
        with TemporaryDirectory() as d:
            base=self.setup(d);client=Fake(raw)
            result=archive(root=d,client=client,probe=lambda b:True)
            self.assertEqual(result["new_stored_video_files"],1)
            row=json.loads((base/"videos.json").read_text())["videos"][0]
            self.assertEqual(row["kind"],"local_mp4")
            self.assertEqual(row["sha256"],hashlib.sha256(raw).hexdigest())
            self.assertEqual((base/row["path"]).read_bytes(),raw)
    def test_site_blocked_zero_new_bytes(self):
        with TemporaryDirectory() as d:
            self.setup(d);result=archive(root=d,client=Fake())
            self.assertEqual(result["new_stored_video_files"],0)
            self.assertEqual(result["errors"],{"robots_or_public_host_denied":1})
    def test_invalid_or_non_playable_not_saved(self):
        with TemporaryDirectory() as d:
            base=self.setup(d)
            result=archive(root=d,client=Fake(b"<html>"+bytes(5500)),probe=lambda b:True)
            self.assertEqual(result["new_stored_video_files"],0)
            self.assertFalse((base/"stored-videos").exists())
        with TemporaryDirectory() as d:
            self.setup(d)
            result=archive(root=d,client=Fake(b"\0\0\0\x18ftyp"+bytes(5500)),
                           probe=lambda b:False)
            self.assertEqual(result["new_stored_video_files"],0)
if __name__=="__main__":unittest.main(verbosity=2)
