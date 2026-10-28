#!/usr/bin/env python3
"""Exact public model ID, CDN hosts, and visible post carousel evidence."""
from collect_imginn_public import allowed_page,allowed_media,profile_verified,media_and_posts

def main():
    assert allowed_page("https://imginn.com/mimmissu17/")
    assert allowed_page("https://imginn.com/p/DQn4BBmkzTz/")
    assert not allowed_page("https://imginn.com/mimm_suz/")
    assert not allowed_page("https://imginn.com/api/private/media?id=1")
    assert allowed_media("https://scontent-ord5-2.cdninstagram.com/v/t51.2885-15/123.jpg?sig=abc")
    for bad in ("https://evil-cdninstagram.com/v/123.jpg",
                "http://scontent-ord5-2.cdninstagram.com/v/123.jpg",
                "https://scontent-ord5-2.cdninstagram.com/private/123.jpg",
                "https://scontent-ord5-2.cdninstagram.com.evil.test/v/123.jpg"):
        assert not allowed_media(bad),bad
    page='''<title>Mimmi(밈미) (@mimmissu17): Posts</title>
    <h1>Mimmi(밈미)</h1><p>@mimmissu17</p>
    <a href="/p/DQn4BBmkzTz/">View post</a>
    <a href="https://scontent-ord5-2.cdninstagram.com/v/t51.2885-15/123.jpg?sig=abc">Download</a>
    <a href="https://scontent-ord5-2.cdninstagram.com/v/t51.2885-15/123.jpg?sig=abc">Download</a>
    <a href="https://evil.test/private.jpg">Download</a>'''
    assert profile_verified(page)
    photos,posts,ok=media_and_posts(page,"https://imginn.com/mimmissu17/")
    assert ok and len(photos)==1 and len(posts)==1,(photos,posts)
    assert not profile_verified(page.replace("@mimmissu17","@wrong_account"))
    post='''<title>Photo by @mimmissu17</title><h1>Mimmi</h1>
    <img data-src="https://scontent-ord5-2.cdninstagram.com/v/t51.2885-15/234.jpg?sig=abc">
    <img src="https://scontent-ord5-2.cdninstagram.com/v/t51.2885-15/345.jpg?sig=abc">'''
    carousel,_,verified=media_and_posts(post,"https://imginn.com/p/DQn4BBmkzTz/",post=True)
    assert verified and len(carousel)==2,carousel
    assert media_and_posts(post.replace("mimmissu17","wrong"),"https://imginn.com/p/DQn4BBmkzTz/",post=True)[2] is False
    print("MIMMI_IMG_INSTA_PROFILE_CAROUSEL_AND_PUBLIC_ONLY_TEST_PASS")

if __name__=="__main__":main()
