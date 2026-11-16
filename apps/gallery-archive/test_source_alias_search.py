#!/usr/bin/env python3
"""Local match/identity regression for public site search. No external requests."""
from source_alias_search import (page_matches,exact_work_in_text,https_page,
                                 source_headings,rotated_work_scope,
                                 rotated_site_scope,crawl_names)
from source_name_ledger import LEDGER
from unittest.mock import patch
import json

def main():
    w="mimmi:djawa-pop-kitty-party"
    assert page_matches(w,"Mimmi DJAWA × Ceyatic Pop Kitty Party","DJAWA × Mimmi photo book")
    assert not page_matches(w,"Mimmi DJAWA Nikke Yuni","Mimmi other album")
    assert not page_matches(w,"Pop Kitty Party","Model XYZ, unrelated photographer")
    assert exact_work_in_text("mimmi:djawa-nikke-yuni","DJAWA Mimmi Nikke Yuni")
    assert not exact_work_in_text("mimmi:djawa-nikke-yuni","Mimmi Nikke Alice")
    assert page_matches("yui:artgravia-677-yui-public-samples",
                        "ArtGravia Vol.677 Yui","Yui 유이 화보")
    assert not page_matches("yui:artgravia-677-yui-public-samples",
                            "ArtGravia Vol.663 Yui","Yui 유이 화보")
    assert not page_matches("yui:yui-meow-public-samples","Other Yui Costume","Yui elsewhere")
    assert not https_page("http://example.org/yui")
    assert not https_page("https://example.org/login")
    assert not https_page("https://example.org/archive.zip")
    assert not https_page("https://127.0.0.1/album/yui")
    assert not https_page("https://10.2.3.4/album/yui")
    assert not https_page("https://169.254.169.254/latest/meta-data")
    assert not https_page("https://metadata.google.internal/secret")
    assert not https_page("https://pub.example.internal/gallery")
    assert not https_page("https://example.org:8080/gallery")
    assert https_page("https://example.org/album/mimmi?preview=1")
    title,context=source_headings("<html><title>Mimmi Pop Kitty Party</title><h1>DJAWA × Mimmi</h1><p>full public preview</p></html>")
    assert "Pop Kitty Party" in title and "Mimmi" in context
    # A page with only OG metadata is still an explicitly named SAME-WORK
    # source; the publisher's image bytes must be checked later.
    meta_only='<html><head><meta property="og:title" content="DJAWA Mimmi Pop Kitty Party">'
    meta_only+='<meta name="description" content="Official Mimmi photo edition"></head></html>'
    meta_heading,meta_context=source_headings(meta_only)
    assert page_matches(w,meta_heading,meta_context)
    assert len(json.loads(LEDGER.read_text())["works"])>=8
    # A fixed 8-work search budget must cover every registered work across
    # successive runs, not shift by only one work and repeat the same 7.
    works=[f'mimmi:work-{i}' for i in range(43)]
    windows=[rotated_work_scope(works,run*3,3,8) for run in range(6)]
    assert len(set(w for window in windows for w in window))==43
    assert set(windows[0]).isdisjoint(set(windows[1]))
    assert windows[0]!=windows[1]
    assert rotated_work_scope(works,3,3,8)==works[8:16]
    assert rotated_work_scope([],0,3,8)==[]
    try:
        rotated_work_scope(works,-3,3,8)
    except ValueError:
        pass
    else:
        raise AssertionError('invalid negative source rotation must fail')
    # A source snippet mentions two work names, but the actual article
    # proves ONLY the second. Prior global visited_urls discarded its URL
    # after the first failed edition check, losing a real image source.
    source="https://public-image-archives.org/mimmi-multiple-editions"
    work_db={'works':{
        'mimmi:djawa-pop-kitty-party':[{'name':'Mimmi Pop Kitty Party'}],
        'mimmi:djawa-nikke-yuni':[{'name':'Mimmi Nikke Yuni'}]},
        'model_names':{'mimmi':[{'name':'Mimmi'}]}}
    def source_or_search(_session,url,timeout=12):
        if url==source:
            return ('<html><title>DJAWA Mimmi Nikke Yuni</title>'
                    '<h1>Mimmi Nikke Yuni</h1><article>Mimmi official Yuni photos</article>'
                    '</html>','ok')
        return '<html><title>image search</title></html>','ok'
    def shared_result(html,engine):
        if 'image search' in html:
            return [{'url':source,
                     'title':'Mimmi Pop Kitty Party and Mimmi Nikke Yuni',
                     'snippet':'DJAWA cosplay official works'}]
        return []
    with patch('source_alias_search.load_html',side_effect=source_or_search),patch(
            'source_alias_search.hits_from_html',side_effect=shared_result):
        result=crawl_names(work_db,'mimmi',per_work=1,max_pages=2,
                           session=object(),delay=0,work_budget=2)
    by_id={v['id']:v['urls'] for v in result['search_results']}
    assert by_id['djawa-pop-kitty-party']==[],result
    assert by_id['djawa-nikke-yuni']==[source],result

    # A newly observed source host must not be stuck permanently behind
    # the same alphabetically first two domains on every scheduled run.
    domains=[f'gallery-{i}.public-photo.example.org' for i in range(5)]
    visits=[rotated_site_scope(domains,run*3,3,2) for run in range(5)]
    assert all(len(x)==2 for x in visits),visits
    assert {site for pair in visits for site in pair}==set(domains),visits
    assert visits[0]!=visits[1]
    assert rotated_site_scope([],0,3)==[]
    try:
        rotated_site_scope(domains,-1,3)
    except ValueError:
        pass
    else:
        raise AssertionError('invalid negative site scope must abort')

    print("PUBLIC_SOURCE_ALIAS_MATCH_AND_IDENTITY_GATES_PASS")

if __name__=="__main__":main()
