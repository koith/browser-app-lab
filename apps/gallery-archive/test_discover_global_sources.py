#!/usr/bin/env python3
"""Deterministic, offline regression checks for the cross-region discovery scanner."""
from discover_global_sources import (
    numbered_entries, normalized, portfolio_entries, visible_portfolio_pages,
    reconcile, run, relevant
)

def main():
    cn = """<html><body>
    <p>Mimmi NO.051 DJAWA Photo Mimmi Rei, Beyond the Heart [97P 1.77GB]</p>
    <p>NO.052 DJAWA Photo Mimmi Asuna the Maid 〖125P〗</p>
    <p>NO.052 DJAWA Photo Mimmi Asuna the Maid 〖125P〗</p>
    <p>NO.251 Other model [500P]</p>
    </body></html>"""
    extracted = numbered_entries(cn, "mimmi")
    assert len(extracted) == 2, extracted
    assert {p["number"]: p["advertised_photos"] for p in extracted} == {51: 97, 52: 125}
    nested = """<ul><li><span>NO.053</span><span> DJAWA Photo Mimmi</span><span> Twilight [88P]</span></li></ul>"""
    assert numbered_entries(nested, "mimmi")[0]["advertised_photos"] == 88
    assert normalized("DJAWA Photo Mimmi Asuna the Maid") == normalized("Asuna the Maid")
    assert not relevant("Yui from another creator", "mimmi")
    assert relevant("심혜성 photographs", "yui")
    assert not relevant("Yuina and Yuiro", "yui")
    assert not relevant("Mimmiana archive", "mimmi")
    mixed="""<h1>Yui SWEETBOX catalogue</h1><ul>
      <li>NO.072 Yui SWTB Vol.65 Present [33P]</li>
      <li>NO.077 Nyangsarang SWTB Vol.83 Ocean [114P]</li>
      <li>NO.078 Miyao Debut [125P]</li>
      <li>NO.079 Yuina unrelated [90P]</li></ul>"""
    assert [p['number'] for p in numbered_entries(mixed,'yui')]==[72]
    assert not numbered_entries('<p>NO.001 Other [20P] NO.002 Yui Green [91P]</p>','yui')
    assert not numbered_entries('<p>NO.008的Yui’s Present标题完整，是说明而不是目录条目。</p>','yui')
    assert numbered_entries('<li>NO.024 SWTB CREAM YUI 【228P3V】</li>','yui')[0]['advertised_photos']==228

    official = """<html><body>
    <h2><a href="/portfolio/asuna-the-maid/">Asuna the Maid</a></h2>
    <a href="https://example.com/portfolio/alien/">Alien content</a>
    <a href="/portfolio-cat/mimmi/page/2/">2</a>
    <a href="/portfolio-cat/mimmi/page/3/">Next</a>
    </body></html>"""
    root = "https://djawaphoto.com/portfolio-cat/mimmi/"
    portfolio = portfolio_entries(official, root)
    assert len(portfolio) == 1 and portfolio[0]["title"] == "Asuna the Maid", portfolio
    pages = visible_portfolio_pages(official, root, root)
    assert len(pages) == 2, pages

    sources = [{"model": "mimmi", "id": "catalogue", "tier": "third_party_catalogue",
                "url": "https://site.test/mimmi/", "items": [{"title": "DJAWA Photo Mimmi Asuna the Maid",
                "advertised_photos": 125, "number": 52}]}]
    leads = reconcile(sources, {"mimmi": {
        normalized("Asuna the Maid"): [{"id": "djawa-asuna-the-maid", "title": "Asuna the Maid",
                                        "stored_public_photos": 10}]}, "yui": {}})
    assert len(leads) == 1
    assert leads[0]["exact_stored_title_matches"][0]["stored_public_photos"] == 10
    assert leads[0]["advertised_counts"][0]["photos"] == 125
    assert leads[0]["discovery_only_not_gallery"]

    class FakeResponse:
        status_code = 200
        headers = {"Content-Type": "text/html; charset=utf-8"}
        def __init__(self, html, url):
            self.text, self.content, self.url = html, html.encode(), url
    class FakeSession:
        headers = {}
        def get(self, url, **kwargs):
            return FakeResponse(cn if "mimmi" in url else
                "<html><body>Yui ゆい NO.001 Green [91P]</body></html>", url)
    registry = {"sources": [
        {"id": "cn-mimmi", "model": "mimmi", "mode": "numbered",
         "tier": "third_party_catalogue", "region": "CN", "url": "https://site.test/mimmi/"},
        {"id": "cn-yui", "model": "yui", "mode": "numbered",
         "tier": "third_party_catalogue", "region": "CN", "url": "https://site.test/yui/"}]}
    result = run(registry, pause=0, session=FakeSession())
    assert result["summary"]["sources_checked"] == 2
    assert result["summary"]["new_photos_stored"] == 0
    assert result["summary"]["gallery_images_added"] == 0
    assert all(x["discovery_only_not_gallery"] for x in result["leads"])
    assert result["summary"]["catalogue_title_groups"] >= 2
    print("GLOBAL_CATALOGUE_DISCOVERY_TEST_PASS", result["summary"])


if __name__ == "__main__":
    main()
