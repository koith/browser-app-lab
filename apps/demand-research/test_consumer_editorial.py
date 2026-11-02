"""Non-sensitive, wholly synthetic regression fixtures for licensed editorial ratings."""
import csv
from io import StringIO
from pathlib import Path
import sys
import pytest
sys.path.insert(0,str(Path(__file__).resolve().parent))
from consumer_editorial import (compile_report, RATING_COLUMNS, PRODUCT_COLUMNS,
                              _read_csv, fetch_source)

def csv_bytes(cols, rows):
    b=StringIO(); w=csv.DictWriter(b,fieldnames=cols);w.writeheader();w.writerows(rows)
    return b.getvalue().encode()

def fixtures():
    products=[]
    for i in range(110):
        cat='robot-vacuums' if i<2 else 'nonfocused-'+str(i)
        products.append(dict(zip(PRODUCT_COLUMNS,[
            cat,'Sample category',f'vacuum-{i}',f'Robot Vacuum Model {i}','',
            '1','4','2','3','2026-01-01','2026-10-01',
            f'https://verdict-reviews.com/product/vacuum-{i}/'])))
    rows=[]
    for i in range(1002):
        rows.append(dict(zip(RATING_COLUMNS,[
            f'product-{i}',f'nonfocused-{i}','reviewer',
            f'https://example.com/reviews/{i}','4','5','4','jsonld','true','true'])))
    extras=[
      ['vacuum-0','robot-vacuums','site-a','https://outlet.example/review/1','5','5','5','jsonld','true','true'],
      ['vacuum-0','robot-vacuums','site-b','https://outlet.example/review/2','4','5','4','jsonld','true','true'],
      ['vacuum-0','robot-vacuums','site-c','https://outlet.example/review/3','4','5','4','article-llm','false','false'],
      ['vacuum-0','robot-vacuums','site-d','https://outlet.example/review/4','','','','unscored','','false'],
      ['vacuum-0','robot-vacuums','site-a','https://outlet.example/review/1','5','5','5','jsonld','true','true'],
      ['vacuum-1','robot-vacuums','site-e','https://outlet.example/review/5','5','5','5','jsonld','false','false'],
    ]
    rows.extend(dict(zip(RATING_COLUMNS,x)) for x in extras)
    return csv_bytes(RATING_COLUMNS,rows),csv_bytes(PRODUCT_COLUMNS,products)

def test_conservative_rating_and_exclusions():
    a,b=fixtures(); r=compile_report(a,b,as_of='2026-11-03');s=r['summary']
    assert s['source_ratings_rows']==1008
    assert s['selected_categories']==1 and s['selected_products']==2
    assert s['selected_review_links']==5 and s['duplicate_source_rows']==1
    assert s['publisher_stated_scores']==2 and s['inferred_scores_excluded']==2
    assert s['unscored_reviews']==1
    p=next(x for x in r['products'] if x['product_id']=='vacuum-0')
    assert p['publisher_stated_mean_5pt']==4.5
    assert len(p['sample_review_urls'])==2
    assert r['dataset']['is_consumer_demand'] is False
    assert r['dataset']['same_person_inferred'] is False
    assert 'site-a' not in str(r)

def test_no_stated_score_is_null_not_zero():
    a,b=fixtures();r=compile_report(a,b,as_of='2026-11-03')
    p=next(x for x in r['products'] if x['product_id']=='vacuum-1')
    assert p['publisher_stated_mean_5pt'] is None
    assert p['inferred_scores_excluded']==1

def test_invalid_schema_date_or_url_fail_closed():
    a,b=fixtures()
    with pytest.raises(ValueError,match='unexpected CSV schema'):
        compile_report(b,a,as_of='2026-11-03')
    with pytest.raises(ValueError,match='invalid as-of date'):
        compile_report(a,b,as_of='2026-15-04')
    with pytest.raises(ValueError,match='allowlisted'):
        fetch_source('https://other.example/reviews.csv')

@pytest.mark.parametrize('bad',[b'',b'product_slug,category_slug\nabc,bcd',b'\xff\xfe\xfa'])
def test_invalid_csv(bad):
    with pytest.raises(ValueError):
        _read_csv(bad,RATING_COLUMNS)

def test_deterministic_and_no_person_records():
    a,b=fixtures()
    r=compile_report(a,b,as_of='2026-11-03')
    assert r==compile_report(a,b,as_of='2026-11-03')
    assert len(r['dataset']['ratings_csv_sha256'])==64
    assert 'author_id' not in str(r) and 'account_url' not in str(r)

def test_selected_categories_are_non_sensitive_and_bounded():
    from consumer_editorial import CATEGORIES
    assert 1<=len(CATEGORIES)<=10
    assert 'adult' not in str(CATEGORIES)
    assert all(len(x)<60 for x in CATEGORIES)
