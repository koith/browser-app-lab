#!/usr/bin/env python3
"""Offline safety tests for the additional public-article photo crawler."""
from crawl_public_article import choose_image,safe_remote,HEART_STEAL

def main():
    assert safe_remote("https://media.example.org/path.jpg")
    for url in ("http://localhost/a.jpg","https://127.0.0.1/a.jpg",
                "https://192.168.1.1/a.jpg","file:///etc/passwd",
                "https://foo.local/image.jpg"):
        assert not safe_remote(url),url
    photo={"alt":"Image 12","src":"https://cdn.example.org/small.jpg",
           "full":"https://cdn.example.org/1200.jpg",
           "href":"https://jjcos.com/post/another/"}
    assert choose_image(photo,HEART_STEAL)==(12,"https://cdn.example.org/1200.jpg")
    assert choose_image({"alt":"Related Item 5","src":"https://example.org/x.jpg"},HEART_STEAL) is None
    assert choose_image({"alt":"Image 1","src":"http://localhost/private.jpg"},HEART_STEAL) is None
    print("PUBLIC_ARTICLE_CRAWLER_FILTER_AND_RESOLUTION_TEST_PASS")
if __name__=="__main__":
    main()
