#!/usr/bin/env python3
from discover_pixibb_search import allowed_article,links,TERMS
def main():
    assert len(TERMS)>=6
    good="https://cosplay.pixibb.com/djawa-photo-mimmi-new-cosplay-photos/"
    assert allowed_article(good)
    assert not allowed_article("https://cosplay.pixibb.com/wp-admin/")
    assert not allowed_article("https://evil.test/djawa-photo-mimmi-new-cosplay-photos/")
    html='''<article><h2><a href="/djawa-photo-mimmi-new-cosplay-photos/">Mimmi DJAWA</a></h2></article>
    <article><h2><a href="/another-cosplayer-summer-photos/">Other model</a></h2></article>
    <article><h2><a href="https://evil.test/album">Mimmi</a></h2></article>'''
    assert links(html,"https://cosplay.pixibb.com")==[good],links(html,"https://cosplay.pixibb.com")
    print("MIMMI_MULTILINGUAL_PUBLIC_SITE_SEARCH_TEST_PASS")
if __name__=="__main__":main()
