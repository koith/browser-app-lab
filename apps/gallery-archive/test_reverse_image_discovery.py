#!/usr/bin/env python3
"""Offline fixture checks for prioritized public-only reverse-image leads."""
import importlib.util
import json
import tempfile
from pathlib import Path

FILE = Path(__file__).with_name("reverse_image_discovery.py")
spec = importlib.util.spec_from_file_location("reverse_image_discovery", FILE)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


def fixture(root):
    for model in ("yui", "mimmi"):
        dest = root / (model + "-gallery")
        dest.mkdir()
        albums = [
            {"id": "tiny", "title": "Real small album", "images": [
                {"url": "stored-albums/tiny/" + "a" * 64 + ".jpg", "sha256": "a" * 64}
            ]},
            {"id": "ai", "title": "[AI Enhanced] fake version", "images": [
                {"url": "stored-albums/ai/" + "b" * 64 + ".jpg", "sha256": "b" * 64}
            ]},
            {"id": "private", "title": "Private URL", "images": [
                {"url": "https://private.example/x.jpg", "sha256": "c" * 64},
                {"url": "stored-albums/../../secrets.jpg", "sha256": "d" * 64}
            ]},
            {"id": "large", "title": "Large public album", "images": [
                {"url": f"stored-albums/large/{i:03d}.webp", "sha256": str(i % 10) * 64}
                for i in range(12)
            ]},
        ]
        (dest / "stored-albums.json").write_text(json.dumps({
            "model": model, "albums": albums
        }))


def main():
    with tempfile.TemporaryDirectory() as path:
        root = Path(path)
        fixture(root)
        seeds = mod.physical_seeds(root)
        assert len(seeds) == 8, seeds  # 1 + 3, twice
        assert seeds[0]["album_id"] == "tiny"
        assert all(s["public_image_url"].startswith(mod.PAGES + "/") for s in seeds)
        assert all("private.example" not in s["public_image_url"] for s in seeds)
        assert all("ai/" not in s["public_image_url"] for s in seeds)
        calls = []

        def pretend(session, url):
            calls.append(url)
            return {"status": "leads_found", "links": [
                {"url": "https://coserbox.com/model/yui" if "/yui-gallery/" in url
                        else "https://coserbox.com/model/mimmi",
                 "label": "Sim Yui photo" if "/yui-gallery/" in url else "Mimmi photo"}]}
        output = mod.discover(root, max_seeds=3, offset=2, delay=0, engine=pretend)
        assert output["seed_queries"] == 3
        assert output["candidate_page_urls"] == 2
        assert not output["gallery_images_added"]
        assert output["research_only_not_acquired"]
        assert len(calls) == 3

    assert mod.identity_supported({"model": "mimmi", "album_title": "Retrospection"},
                                  {"url": "https://www.4khd.com/content/jvid-other",
                                   "label": "JVID Li Feier"}) is False
    assert mod.identity_supported({"model": "mimmi", "album_title": "Nikke Yuni"},
                                  {"url": "https://cosmeitu.com/mimmi/nikke",
                                   "label": "Mimmi Nikke Yuni"}) is True
    assert mod.identity_supported({"model": "yui", "album_title": "Teddy Bear"},
                                  {"url": "https://coserbox.com/yui/teddy-bear",
                                   "label": "Yui SWEETBOX Teddy Bear"}) is True
    assert mod.identity_supported({"model": "yui", "album_title": "Teddy Bear"},
                                  {"url": "https://coserbox.com/yui-nomodel",
                                   "label": "Other model"}) is False

    html = ('<a href="https://www.google.com/url?q=https%3A%2F%2F'
            'cosmeitu.com%2Fshow%2Fmimmi&sa=U">Mimmi original</a>'
            '<a href="javascript:alert(1)">attack</a>'
            '<a href="https://unknown.example/pic.jpg">untrusted</a>'
            '<a href="https://cosmeitu.com/show/mimmi">duplicate</a>')
    leads = mod.leads_from_html(html)
    assert len(leads) == 1, leads
    assert leads[0]["label"] == "Mimmi original"
    assert mod.untrack("http://cosmeitu.com/mimmi") is None
    assert mod.untrack("https://private.example/path") is None
    assert mod.untrack("https://x:secret@cosmeitu.com/mimmi") is None

    class FakeResponse:
        status_code = 200
        url = "https://www.google.com/search?vsrid=abc"
        headers = {"Content-Type": "text/html"}
        text = html

    class FakeSession:
        def get(self, endpoint, params, **kw):
            assert endpoint.startswith("https://lens.google.com/")
            assert "url" in params and params["url"].startswith("https://")
            assert kw["allow_redirects"] is True
            return FakeResponse()

    result = mod.lens_query(FakeSession(), "https://koith.github.io/example.jpg")
    assert result["status"] == "leads_found"
    assert len(result["links"]) == 1

    class TinEyeResponse:
        status_code = 200
        headers = {"Content-Type": "application/json"}
        def json(self):
            return {"matches": [
                {"score": 99.0, "width": 2800, "height": 3600,
                 "backlinks": [{"backlink": "https://www.4khd.com/show/mimmi"}]},
                {"score": 20.0, "backlinks": [
                    {"backlink": "https://cosmeitu.com/weak-match"}]}
            ]}
    class TinEyeSession:
        def get(self, endpoint, params, **kw):
            assert endpoint == "https://tineye.com/api/v1/result_json/"
            assert params["page"] == 1
            return TinEyeResponse()
    tin = mod.tineye_query(TinEyeSession(), "https://koith.github.io/photo.jpg")
    assert tin["status"] == "leads_found" and len(tin["links"]) == 1, tin
    assert tin["links"][0]["visual_match_score"] == 99
    class MultiEngineSession:
        def get(self, endpoint, params, **kw):
            if "lens.google" in endpoint:
                return FakeResponse()
            if "tineye" in endpoint:
                return TinEyeResponse()
            class NoYandex:
                status_code = 403
                url = "https://www.bing.com/images/search"
            return NoYandex()
    both = mod.multi_search(MultiEngineSession(), "https://koith.github.io/photo.jpg")
    assert both["engine_statuses"]["yandex"] == "http_403", both
    assert both["engine_statuses"]["tineye"] == "leads_found", both
    assert len(both["links"]) == 2, both

    class BingResponse:
        url = "https://www.bing.com/images/search?test=1"
        status_code = 200
        headers = {"Content-Type": "text/html"}
        content = b"<a href='https://www.4kgirl.com/mimmi'>Mimmi public set</a>"
        text = content.decode()
    class BingSession:
        def get(self, endpoint, params, **kw):
            assert endpoint == "https://www.bing.com/images/search"
            assert params["q"].startswith("imgurl:https://")
            assert params["iss"] == "sbi"
            assert kw["allow_redirects"] is True
            return BingResponse()
    found = mod.bing_visual_query(BingSession(), "https://koith.github.io/photo.jpg")
    assert found["status"] == "leads_found" and len(found["links"]) == 1, found
    assert found["links"][0]["url"].startswith("https://www.4kgirl.com/")
    print("GALLERY_REVERSE_IMAGE_DISCOVERY_FIXTURE_PASS")


if __name__ == "__main__":
    main()
