#!/usr/bin/env python3
"""Local match/identity regression for public site search. No external requests."""
from source_alias_search import page_matches,exact_work_in_text,https_page,source_headings,rotated_work_scope
from source_name_ledger import LEDGER
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
    assert https_page("https://example.org/album/mimmi?preview=1")
    title,context=source_headings("<html><title>Mimmi Pop Kitty Party</title><h1>DJAWA × Mimmi</h1><p>full public preview</p></html>")
    assert "Pop Kitty Party" in title and "Mimmi" in context
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
    print("PUBLIC_SOURCE_ALIAS_MATCH_AND_IDENTITY_GATES_PASS")

if __name__=="__main__":main()
