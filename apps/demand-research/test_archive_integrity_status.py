"""Synthetic private archive readback inventory: no real SNS posts or secrets."""
import json

import pytest
from demand_archive import sha256
from test_demand_archive import FakeCloud,post
from inspect_terabox_status import inspect,MAX_SAMPLED_MEDIA_BYTES


@pytest.fixture(autouse=True)
def private_synthetic_environment(monkeypatch):
    monkeypatch.setenv("RCLONE_CONFIG_ARCHIVE_COOKIE","synthetic")
    monkeypatch.setattr("demand_archive.time.sleep",lambda _:None)


def archive_with_photo(size=23):
    cloud=FakeCloud()
    p=post()
    raw=b"x"*size
    p["media"]=[{"key":"posts/"+p["id"]+"/media/0001.jpg",
                 "mime":"image/jpeg","bytes":len(raw),
                 "sha256":sha256(raw),"remote_verified":True}]
    p["media_expected"]=p["media_saved"]=1
    cloud.save_post(p,[raw])
    return cloud,p,raw


def test_private_inventory_reports_exact_media_readback_without_text(capsys):
    cloud,p,_=archive_with_photo()
    result=inspect(cloud,sample_size=8)
    assert result["sample_valid"]==1
    assert result["media_sha_readback_verified"]==1
    assert result["media_sha_readback_unverified"]==0
    assert result["full_integrity_claim"] is False
    log=capsys.readouterr().out
    assert p["id"] not in log
    assert p["source_url"] not in log
    assert "PRIVATE_ARCHIVE_READ_ONLY_SUMMARY" in log


def test_corrupt_original_media_is_unverified_not_claimed_readback_pass():
    cloud,p,_=archive_with_photo()
    cloud.objects[p["media"][0]["key"]]=b"unexpected other bytes"
    result=inspect(cloud,sample_size=8)
    assert result["sample_valid"]==1  # original post.json remains intact
    assert result["media_sha_readback_verified"]==0
    assert result["media_sha_readback_unverified"]==1


def test_large_original_skipped_under_explicit_byte_budget():
    cloud,p,_=archive_with_photo(2_000_001)
    result=inspect(cloud,sample_size=8)
    assert result["media_sha_readback_verified"]==0
    assert result["media_sha_readback_unverified"]==0
    assert result["media_sample_skipped_large_or_unsafe"]==1
    assert result["media_sample_byte_budget"]==MAX_SAMPLED_MEDIA_BYTES
    assert result["full_integrity_claim"] is False
