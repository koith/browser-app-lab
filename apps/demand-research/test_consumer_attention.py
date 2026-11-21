"""Synthetic-only Wikimedia 14-day pageview aggregate validation."""
from datetime import date,timedelta
from pathlib import Path
import sys
import pytest

sys.path.insert(0,str(Path(__file__).resolve().parent))
from consumer_attention import ARTICLES, _day_values, process, fetch, save


def fixture(as_of="2026-11-03"):
    end=date.fromisoformat(as_of)-timedelta(days=3)
    dates=_day_values(end)
    return {article:{"items":[{
        "project":"en.wikipedia","article":article,"access":"all-access",
        "agent":"user","granularity":"daily","timestamp":day+"00",
        "views":(i+1)*100+j*5
    } for j,day in enumerate(dates)]}
    for i,(_,_,article,_) in enumerate(ARTICLES)}


def test_aggregate_two_nonoverlapping_weeks():
    out=process(fixture(),as_of="2026-11-03")
    assert out["dataset"]["window_start"]=="2026-10-18"
    assert out["dataset"]["window_end"]=="2026-10-31"
    assert out["dataset"]["is_purchases"] is False
    assert out["dataset"]["is_demand"] is False
    assert out["dataset"]["contains_individuals"] is False
    assert len(out["topics"])==6
    first=out["topics"][0]
    assert first["latest_7d_views"]==sum(100+j*5 for j in range(7,14))
    assert first["previous_7d_views"]==sum(100+j*5 for j in range(7))
    assert first["difference_views"]>0
    assert len(first["daily"])==14


def test_aggregate_report_contains_only_daily_counts_not_people():
    obj=process(fixture(),as_of="2026-11-03")
    assert "user_id" not in str(obj)
    assert "email" not in str(obj)
    assert obj["dataset"]["existing_sns_pipeline_connected"] is False
    assert all(topic["wiki_url"].startswith("https://en.wikipedia.org/wiki/")
               for topic in obj["topics"])


def test_incomplete_day_fails_closed():
    source=fixture()
    source[ARTICLES[0][2]]["items"].pop()
    with pytest.raises(ValueError,match="incomplete"):
        process(source,as_of="2026-11-03")


def test_duplicate_and_invalid_count_rejected():
    source=fixture()
    source[ARTICLES[0][2]]["items"].append(dict(source[ARTICLES[0][2]]["items"][0]))
    with pytest.raises(ValueError,match="duplicate"):
        process(source,as_of="2026-11-03")
    source=fixture();source[ARTICLES[0][2]]["items"][0]["views"]=-5
    with pytest.raises(ValueError,match="invalid daily"):
        process(source,as_of="2026-11-03")


def test_source_shape_wrong_article_fails():
    source=fixture()
    source[ARTICLES[0][2]]["items"][0]["article"]="Anonymous_person"
    with pytest.raises(ValueError,match="shape"):
        process(source,as_of="2026-11-03")


def test_exact_six_topic_set():
    source=fixture();source["Unverified"]=source.pop(ARTICLES[0][2])
    with pytest.raises(ValueError,match="exact six"):
        process(source,as_of="2026-11-03")


def test_fetch_refuses_unreviewed_articles_without_network():
    with pytest.raises(ValueError,match="outside the reviewed allowlist"):
        fetch("Private_person", "20261018", "20261031")


def test_rolling_window_is_reproducible(tmp_path):
    report=process(fixture(),as_of="2026-11-03")
    assert report==process(fixture(),as_of="2026-11-03")
    out=tmp_path/"attention.json";save(report,out)
    assert out.is_file()
    assert len(out.read_text())<20000


def test_reject_robot_vacuum_redirect_alias():
    # The redirect alias had only 7 weekly views versus 497 on the real article.
    canonical = next(article for key, _, article, _ in ARTICLES if key == "robotvac")
    assert canonical == "Robotic_vacuum_cleaner"
    assert "Robot_vacuum_cleaner" not in [article for _,_,article,_ in ARTICLES]
