#!/usr/bin/env python3
"""Mimmi official-linked public promo URL allowlist and parser tests."""
from bs4 import BeautifulSoup
import collect_gumroad_public as m

def main():
    assert m.product_url("https://djawaphoto.gumroad.com/l/abc123")
    for bad in ["https://other.gumroad.com/l/abc123","https://djawaphoto.gumroad.com/checkout/abc",
                "http://djawaphoto.gumroad.com/l/abc123",
                "https://djawaphoto.gumroad.com/private/download/file"]:
        assert not m.product_url(bad),bad
    p="<a href='https://djawaphoto.gumroad.com/l/abcdef'>Buy on Gumroad</a>"
    assert m.from_portfolio(p,"https://djawaphoto.com/portfolio/example/")==["https://djawaphoto.gumroad.com/l/abcdef"]
    html='''<meta property="og:image" content="https://public-files.gumroad.com/fake-public-image.jpg">
    <img src="https://assets.gumroad.com/published-thumbnail.jpg">
    <img src="https://evil.example/private.jpg">
    <a href="/some-private-download?token=abc">Download</a>'''
    actual=m.promo_candidates(html,"https://djawaphoto.gumroad.com/l/abcdef")
    assert len(actual)==2,actual
    for url in actual:assert m.preview_url(url)
    assert not m.preview_url("https://public-files.gumroad.com.evil.test/foo.jpg")
    assert not m.preview_url("https://assets.gumroad.com/private.js")
    assert not m.preview_url("http://public-files.gumroad.com/fake.jpg")
    print("MIMMI_GUMROAD_PUBLIC_PROMO_PARSER_PASS")

if __name__=="__main__":main()
