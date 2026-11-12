"""Offline mocked public API indexing proof; never contacts SNS in CI."""
from datetime import datetime, timezone
import sqlite3
import account_index
import account_index_sources as sources


NOW=int(datetime(2026,11,2,14,0,tzinfo=timezone.utc).timestamp())


def fake_result(term,begin,end,duplicate=False):
    did="did:plc:syntheticexample123"
    stamp=datetime.fromtimestamp(begin+min(1800,end-begin-1),timezone.utc).isoformat()
    p={"uri":"at://"+did+"/app.bsky.feed.post/qa123",
       "author":{"did":did,"handle":"qa-account.bsky.social"},
       "record":{"text":"공개 글: "+term,"createdAt":stamp},
       "indexedAt":stamp,"labels":[]}
    return {"posts":[p,p] if duplicate else [p],"hitsTotal":1}


def test_rows_require_original_validated_id_author_term_and_window():
    begin=NOW-3600;end=NOW
    good=fake_result("섹트",begin,end)
    result=sources.validated_rows(good,"섹트",begin,end)
    assert len(result)==1
    assert result[0]["profile_url"].startswith("https://bsky.app/profile/did:plc:")
    good["posts"][0]["author"]["did"]="did:plc:forgedauthor"
    assert sources.validated_rows(good,"섹트",begin,end)==[]
    good["posts"][0]["author"]["did"]="did:plc:syntheticexample123"
    good["posts"][0]["record"]["text"]="not a matching term"
    assert sources.validated_rows(good,"섹트",begin,end)==[]


def test_bounded_batch_stores_profiles_not_text_and_resumes(tmp_path):
    db=str(tmp_path/"private.sqlite3")
    calls=[]
    def mock(term,start,end):
        calls.append((term,start,end))
        return fake_result(term,start,end)
    first=sources.run_batch(db,fetcher=mock,max_requests=6,now=NOW)
    assert first["requests"]==6
    assert first["accepted"]==6
    assert account_index.status(db)["accounts"]==1
    assert account_index.status(db)["source_rows"]==1  # identical original URI across terms deduplicates
    assert sources.run_batch(db,fetcher=mock,max_requests=6,now=NOW+120)["skipped_recent_run"]
    second=sources.run_batch(db,fetcher=mock,max_requests=6,now=NOW+3600)
    assert second["requests"]==6
    assert account_index.status(db)["accounts"]==1
    assert "done" in sources.coverage(db)
    with sqlite3.connect(db) as conn:
        raw=" ".join(str(x) for x in conn.iterdump())
        assert "공개 글:" not in raw
        assert "qa-account.bsky.social" not in raw  # canonical DID, not mutable handle


def test_saturation_is_not_misreported_as_complete(tmp_path):
    db=str(tmp_path/"private.sqlite3")
    def saturated(term,start,end):
        p=fake_result(term,start,end)["posts"][0]
        return {"posts":[p]*100,"hitsTotal":1000}
    result=sources.run_batch(db,fetcher=saturated,max_requests=6,now=NOW)
    assert result["requests"]==6
    assert sources.coverage(db).get("incomplete",0)>=3 or sources.coverage(db).get("split",0)>=1


def test_source_failure_records_and_limited_retries(tmp_path):
    db=str(tmp_path/"private.sqlite3")
    def broken(term,start,end):
        raise ConnectionError("fake offline rate limit")
    result=sources.run_batch(db,fetcher=broken,max_requests=3,now=NOW)
    assert result["errors"]==3
    assert sources.coverage(db)["pending"]>=3


def test_public_search_falls_back_to_second_official_host(monkeypatch):
    from urllib.error import HTTPError
    import io,json
    called=[]
    class Response:
        def __enter__(self):return self
        def __exit__(self,*a):return False
        def read(self,n):return json.dumps({"posts":[]}).encode()
    def urlopen(request,timeout):
        called.append(request.full_url)
        if len(called)==1:
            raise HTTPError(request.full_url,403,"forbidden",{},None)
        return Response()
    monkeypatch.setattr(sources,"urlopen",urlopen)
    body=sources.fetch_public("섹트",NOW-3600,NOW)
    assert body=={"posts":[]}
    assert len(called)==2
    assert called[0].startswith("https://api.bsky.app/")
    assert called[1].startswith("https://public.api.bsky.app/")


def test_all_requested_terms_accepted_by_public_index_and_capture(monkeypatch):
    """Regression: 섹블 was in fast capture TERMS but rejected by its search adapter.

    All four requests remain bounded, use only official public API hosts and
    validate the original DID/URI and the posted timestamp.
    """
    import demand_capture_job as capture
    assert tuple(sources.TERMS)==tuple(capture.TERMS)
    calls=[]
    class Response:
        def __enter__(self): return self
        def __exit__(self,*unused): return False
        def read(self,n): return b'{"posts":[]}'
    def mock(request,timeout):
        calls.append(request.full_url)
        return Response()
    monkeypatch.setattr(sources,"urlopen",mock)
    for term in capture.TERMS:
        assert sources.fetch_public(term,NOW-900,NOW)=={"posts":[]}
        valid=sources.validated_rows(fake_result(term,NOW-900,NOW),
                                     term,NOW-900,NOW)
        assert len(valid)==1
        assert valid[0]["source_url"].startswith("https://bsky.app/profile/")
    assert len(calls)==4
    assert all(url.startswith("https://api.bsky.app/xrpc/") for url in calls)
