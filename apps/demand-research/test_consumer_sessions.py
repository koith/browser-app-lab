"""Regression: synthetic sessions only; real source is verified separately in CI."""
import csv
from io import BytesIO, StringIO
from pathlib import Path
import sys
from zipfile import ZipFile
import pytest
sys.path.insert(0, str(Path(__file__).resolve().parent))
from consumer_sessions import (EXPECTED_COLUMNS, analyze_csv, zip_csv,
                               _wilson, _bucket, write_json)


def fixture(n=80):
    text=StringIO()
    writer=csv.DictWriter(text, fieldnames=EXPECTED_COLUMNS)
    writer.writeheader()
    for i in range(n):
        row={field:"0" for field in EXPECTED_COLUMNS}
        row.update({
            "Month": ["Nov","Dec","Feb"][i % 3],
            "VisitorType": ["Returning_Visitor","New_Visitor","Other"][i % 3],
            "Weekend": "TRUE" if i % 2 else "FALSE",
            "Revenue": "TRUE" if i % 5 == 0 else "FALSE",
            "ProductRelated": str([0,1,8,23,50][i % 5]),
            "ProductRelated_Duration": str(i * 10.5),
        })
        writer.writerow(row)
    return text.getvalue().encode()


def test_aggregation_and_privacy():
    report=analyze_csv(fixture(), strict_original=False)
    assert report["summary"]["sessions"] == 80
    assert report["summary"]["purchases"] == 16
    assert report["summary"]["conversion_pct"] == 20
    assert len(report["segments"]["month"]) == 3
    assert sum(x["sessions"] for x in report["segments"]["month"]) == 80
    assert sum(x["purchases"] for x in report["segments"]["visitor"]) == 16
    assert len(report["segments"]["product_pages"]) == 5
    assert len(report["dataset"]["csv_sha256"]) == 64
    assert report["dataset"]["contains_person_identifiers"] is False
    assert report["dataset"]["is_current_data"] is False
    assert "session_rows" not in str(report)


def test_reproducible_report_without_raw_individuals(tmp_path):
    a=analyze_csv(fixture(), strict_original=False)
    assert a==analyze_csv(fixture(), strict_original=False)
    file=tmp_path/"aggregate.json"
    write_json(a,file)
    text=file.read_text()
    assert '"sessions": 80' in text
    assert "Administrative_Duration" not in text
    assert "ProductRelated_Duration" not in text


def test_wilson_is_bounded_and_zero_safe():
    assert _wilson(0,0) is None
    assert _wilson(0,100)[0] == 0
    assert _wilson(100,100)[1] == 100
    low, high=_wilson(16,80)
    assert low<20<high


def test_page_bucket_boundaries():
    assert [_bucket(n) for n in (0,1,5,6,15,16,40,41)] == [
        "0","1–5","1–5","6–15","6–15","16–40","16–40","41+"]


def test_historic_original_invariant_fails_on_fake_data():
    with pytest.raises(ValueError, match="official historical dataset changed"):
        analyze_csv(fixture(), strict_original=True)


def test_reject_schema_wrong_columns():
    data=fixture().replace(b"ProductRelated,",b"ProductVisitCount,")
    with pytest.raises(ValueError,match="unexpected UCI shopping CSV schema"):
        analyze_csv(data,strict_original=False)


@pytest.mark.parametrize("field,value,error",[
    ("Revenue","yes","invalid Revenue"),
    ("Weekend","0","invalid Weekend"),
    ("Month","Jum","unexpected visitor"),
    ("VisitorType","Missing","unexpected visitor"),
    ("ProductRelated","-1","out-of-range"),
    ("ProductRelated_Duration","nan","out-of-range"),
])
def test_fail_closed_on_invalid_input(field,value,error):
    src=fixture(5).decode()
    rows=list(csv.DictReader(StringIO(src)))
    rows[0][field]=value
    buf=StringIO();w=csv.DictWriter(buf,fieldnames=EXPECTED_COLUMNS);w.writeheader();w.writerows(rows)
    with pytest.raises(ValueError,match=error):
        analyze_csv(buf.getvalue().encode(),strict_original=False)


def test_zip_reader_is_in_memory_and_bounded():
    blob=BytesIO()
    with ZipFile(blob,"w") as zip:
        zip.writestr("online_shoppers_intention.csv",fixture())
    assert zip_csv(blob.getvalue())==fixture()
    with pytest.raises(ValueError,match="invalid UCI zip size"):
        zip_csv(b"")
    empty=BytesIO()
    with ZipFile(empty,"w") as zip:
        zip.writestr("other.csv",fixture())
    with pytest.raises(ValueError,match="missing or oversized"):
        zip_csv(empty.getvalue())


def test_no_session_identifiers_or_current_claims():
    report=analyze_csv(fixture(),strict_original=False)
    assert report["dataset"]["is_current_market_demand"] is False
    assert report["dataset"]["unit"].startswith("historical website session")
    assert report["dataset"]["existing_sns_pipeline_connected"] is False
    assert "visitor_id" not in str(report)
    assert "email" not in str(report)
