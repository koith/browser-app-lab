"""No live network or private credentials; synthetic authenticated ciphertext QA."""
import hashlib
import sqlite3
from datetime import datetime,timezone,timedelta

import pytest
import account_index
import account_index_bootstrap as boot


def fixture_db(tmp_path, name="sample.sqlite3"):
    p=tmp_path/name
    account_index.sync_catalog(str(p),[{
        "id":"test-public-post-1",
        "platform":"x",
        "profile_url":"https://x.com/qa_test_a",
        "text":"Synthetic QA only; no real account",
    }])
    with sqlite3.connect(str(p)) as db:
        db.execute("PRAGMA wal_checkpoint(TRUNCATE)")
    return p


def test_encrypted_index_roundtrip_does_not_leak_source_rows(tmp_path):
    path=fixture_db(tmp_path)
    raw=path.read_bytes()
    key=b"s"*32
    digest=hashlib.sha256(raw).hexdigest()
    cipher=boot.encrypt_snapshot(raw,key,"42547929782",digest)
    assert cipher.startswith(boot.MAGIC)
    assert raw not in cipher
    assert b"qa_test_a" not in cipher
    assert digest.encode() not in cipher
    opened=boot.decrypt_snapshot(cipher,key)
    assert opened["run_id"]=="42547929782"
    assert opened["sha"]==digest
    assert opened["accounts"]==1
    assert opened["source_rows"]==1
    assert opened["payload"]==raw


def test_encrypted_index_rejects_wrong_key_tamper_sha_and_sqlite(tmp_path):
    raw=fixture_db(tmp_path).read_bytes()
    good=b"a"*32
    digest=hashlib.sha256(raw).hexdigest()
    cipher=boot.encrypt_snapshot(raw,good,"42547929782",digest)
    with pytest.raises(ValueError):
        boot.decrypt_snapshot(cipher,b"b"*32)
    damaged=bytearray(cipher)
    damaged[-10]^=0x20
    with pytest.raises(ValueError):
        boot.decrypt_snapshot(bytes(damaged),good)
    with pytest.raises(ValueError):
        boot.encrypt_snapshot(raw,good,"42547929782","0"*64)
    with pytest.raises(ValueError):
        boot.encrypt_snapshot(b"not-sqlite",good,"42547929782",
                              hashlib.sha256(b"not-sqlite").hexdigest())
    with pytest.raises(ValueError):
        boot.decrypt_snapshot(b"index credentials as raw bytes",good)


def test_index_release_tags_are_bounded_and_utc_only():
    day=datetime(2026,11,9,12,0,tzinfo=timezone.utc)
    assert boot.tag_for_date(day)=="intersection-index-boot-20261109"
    assert boot.tag_for_date(day-timedelta(days=1))=="intersection-index-boot-20261108"
    assert boot.TAG.fullmatch("intersection-index-boot-20261109")
    assert not boot.TAG.fullmatch("intersection-index-boot-20261109/../../")
    with pytest.raises(ValueError):
        boot.release_tag("https://evil.invalid/trick")


def test_authenticated_index_cold_restore_wont_erase_good_rows(tmp_path,monkeypatch):
    p=fixture_db(tmp_path)
    raw=p.read_bytes()
    key=b"k"*32
    sealed=boot.encrypt_snapshot(raw,key,"42547929782",hashlib.sha256(raw).hexdigest())
    def snapshot(secret,now=None,lookback_days=7):
        out=boot.decrypt_snapshot(sealed,secret)
        out["age_days"]=1
        return out
    monkeypatch.setattr(boot,"find_latest_cipher",snapshot)
    target=tmp_path/"gateway-view.sqlite3"
    first=boot.restore_local(str(target),key)
    assert first["state"]=="restored"
    assert first["accounts"]==1 and first["source_rows"]==1
    with sqlite3.connect(str(target)) as db:
        meta=dict(db.execute("SELECT key,value FROM index_meta"))
    assert meta["last_imported_index_run"]=="42547929782"
    assert meta["last_imported_index_sha"]==hashlib.sha256(raw).hexdigest()
    assert boot.restore_local(str(target),key)["state"]=="already_populated"
    with sqlite3.connect(str(target)) as db:
        assert db.execute("SELECT count(*) FROM accounts").fetchone()[0]==1


def test_no_authenticated_snapshot_means_no_false_restore(tmp_path,monkeypatch):
    def unavailable(key,now=None,lookback_days=7):
        raise RuntimeError("not found")
    monkeypatch.setattr(boot,"find_latest_cipher",unavailable)
    path=tmp_path/"never-restored.sqlite3"
    with pytest.raises(RuntimeError):
        boot.restore_local(str(path),b"z"*32)
    assert not path.exists()



def test_encrypted_release_asset_rejects_wrong_origin_and_duplicate_name():
    tag="intersection-index-boot-20261109"
    url="https://github.com/koith/browser-app-lab/releases/download/"+tag+"/index.enc"
    asset={"name":"index.enc","browser_download_url":url,"size":500}
    release={"tag_name":tag,"draft":False,"prerelease":True,"assets":[asset]}
    assert boot._asset(release,tag)==asset
    with pytest.raises(ValueError):
        boot._asset({**release,"assets":[{**asset,"browser_download_url":
                    "https://untrusted.invalid/index.enc"}]},tag)
    with pytest.raises(ValueError):
        boot._asset({**release,"assets":[asset,asset]},tag)
    with pytest.raises(ValueError):
        boot._asset({**release,"prerelease":False},tag)


def test_existing_sealed_daily_checkpoint_is_readback_verified_not_overwritten(
        tmp_path,monkeypatch):
    path=fixture_db(tmp_path)
    raw=path.read_bytes()
    key=b"x"*32
    wrapped=boot.encrypt_snapshot(raw,key,"42547929782",hashlib.sha256(raw).hexdigest())
    monkeypatch.setattr(boot,"release_tag",lambda tag,token=None:{"tag_name":tag})
    monkeypatch.setattr(boot,"download_cipher",lambda release,tag:wrapped)
    result=boot.publish_daily(wrapped,key,token="synthetic-github-token")
    assert result["new_upload"] is False
    assert result["accounts"]==1 and result["remote_sha256"] is True
