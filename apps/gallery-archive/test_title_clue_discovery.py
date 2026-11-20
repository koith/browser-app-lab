#!/usr/bin/env python3
import tempfile
from pathlib import Path
from title_clue_discovery import title_clues,query_families,Queue,search_hits,related_links,internal_search_links,plan

def main():
    c=title_clues("ARTGRAVIA VOL.639 Yui (118 photos)",["Yui","심유이"])
    assert ("vol","639") in c["editions"] and all(n!="118" for _,n in c["editions"]),c
    q=query_families("ARTGRAVIA VOL.639 Yui",["Yui","심유이"])
    assert "AG639" in q["compact_code"] and "639" in q["number"] and "심유이" in q["model"]
    q=query_families("DJAWA Summer Night",["Sample","샘플"])
    assert "여름" in q["translated_word"] and "夏" in q["translated_word"]
    assert "DJAWA" in q["publisher"]
    assert ("code","22") in title_clues("SWTB22 Example",["Example"])["editions"]
    raw='<div id="search"><a href="/url?q=https%3A%2F%2Fcatalog.example.org%2Fa">A</a><a href="https://catalog.example.org/b">B</a></div>'
    assert len(search_hits(raw,"google"))==2
    raw='<li class="serp-item"><a href="https://catalog.example.org/a">A</a></li>'
    assert len(search_hits(raw,"yandex"))==1
    links=related_links('<a href="/page/2" rel="next">next</a><a href="/model/sample">Sample</a>','https://catalog.example.org/a',{"sample"})
    assert len(links)==2
    assert len(related_links('<h2><a href="/portfolio/x">Unlabelled edition</a></h2>','https://catalog.example.org/model/sample',{"sample"},listing=True))==1
    assert internal_search_links('<form action="/" method="get"><input name="s" type="search"></form>','https://catalog.example.org/a',["sample"])==["https://catalog.example.org/?s=sample"]
    with tempfile.TemporaryDirectory() as tmp:
        path=Path(tmp)/"q.db"
        q=Queue(path);q.add("search","Sample","google");q.add("search","Other","yandex")
        first=q.next();q.finish(first[0],"blocked","robots_disallowed")
        q.add("page","https://catalog.example.org/a")
        q.db.close()
        q=Queue(path)
        assert q.next()[1]=="page"
        assert q.report()["queue"]["search:blocked"]==1
        q.db.close()
    for model in ("yui","mimmi"):
        _,_,records,queries,types=plan(model)
        assert records and len(queries)>len(records), (model,len(records),len(queries))
        assert "model" in types and "publisher" in types
        print("TITLE_CLUE_CORPUS",model,len(records),len(queries),types)
    print("TITLE_CLUE_REGRESSION_PASS")
if __name__=="__main__":main()
