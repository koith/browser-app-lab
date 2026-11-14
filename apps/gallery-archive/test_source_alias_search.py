#!/usr/bin/env python3
"""Local match/identity regression for public site search. No external requests."""
from source_alias_search import page_matches,exact_work_in_text,https_page,source_headings
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
    print("PUBLIC_SOURCE_ALIAS_MATCH_AND_IDENTITY_GATES_PASS")

if __name__=="__main__":main()
