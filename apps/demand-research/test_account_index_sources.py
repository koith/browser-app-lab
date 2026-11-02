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
