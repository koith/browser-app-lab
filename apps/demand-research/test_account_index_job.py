"""Offline cloud snapshot tests: state is private and pointer advances last."""
import hashlib
import json
import sqlite3
import pytest
import account_index
import account_index_job as job


def make_db(tmp_path):
    p=tmp_path/"account.sqlite3"
    account_index.sync_catalog(str(p),[{"id":"qa-post","platform":"x",
      "profile_url":"https://x.com/test_qa","text":"SENSITIVE_DO_NOT_PRINT"}])
    return p


def test_snapshot_checkpoints_exact_remote_readback(tmp_path,monkeypatch):
    db=make_db(tmp_path)
    cloud={}
    def fake_cmd(args,*,data=None,timeout=180):
        if args[0]=="copyto":
            cloud[args[2]]=__import__("pathlib").Path(args[1]).read_bytes()
        elif args[0]=="rcat":
            cloud[args[1]]=data
        else: raise AssertionError("unexpected rclone call")
        return b""
    monkeypatch.setattr(job,"command",fake_cmd)
    monkeypatch.setattr(job,"read_remote",lambda path,limit,optional=False:cloud.get(path))
    result=job.create_snapshot(db,"123456789")
    assert result["file"]=="snapshot-123456789.sqlite3"
    assert result["sha256"]==hashlib.sha256(db.read_bytes()).hexdigest()
    assert list(cloud)==[job.REMOTE+"/snapshots/snapshot-123456789.sqlite3"]


def test_corrupt_remote_snapshot_refuses_pointer(tmp_path,monkeypatch):
    db=make_db(tmp_path)
    monkeypatch.setattr(job,"command",lambda *a,**kw:b"")
    monkeypatch.setattr(job,"read_remote",lambda *a,**kw:b"corrupt")
    with pytest.raises(RuntimeError,match="readback mismatch"):
        job.create_snapshot(db,"123456789")


def test_manifest_path_fails_closed(monkeypatch):
    monkeypatch.setattr(job,"read_remote",lambda *a,**k:json.dumps({
      "file":"../../other.sqlite3","sha256":"a"*64}).encode())
    with pytest.raises(ValueError,match="unsafe"):
        job.latest_manifest()


def test_durable_snapshot_requires_private_cloud_env(tmp_path,monkeypatch):
    monkeypatch.delenv("RCLONE_CONFIG_ARCHIVE_COOKIE",raising=False)
    with pytest.raises(RuntimeError,match="credential"):
        job.run()


def test_immutable_manifest_write_and_latest_selection(tmp_path,monkeypatch):
    cloud={}
    def fake_command(args,*,data=None,timeout=180):
        if args[0]=="copyto":
            cloud[args[2]]=__import__("pathlib").Path(args[1]).read_bytes()
            return b""
        if args[0]=="lsf":
            return b"manifest-123456789.json\nmanifest-123456788.json\n"
        raise AssertionError("mutable latest.json overwrite must not be called")
    monkeypatch.setattr(job,"command",fake_command)
    monkeypatch.setattr(job,"read_remote",lambda path,limit,optional=False:cloud.get(path))
    previous={"file":"snapshot-123456788.sqlite3","sha256":"b"*64}
    cloud[job.REMOTE+"/manifests/manifest-123456788.json"]=json.dumps(previous).encode()
    current={"file":"snapshot-123456789.sqlite3","sha256":"a"*64}
    result=job.publish_manifest(tmp_path,current,"123456789")
    assert result["file"]==current["file"]
    assert job.latest_manifest()["file"]==current["file"]
    assert job.REMOTE+"/latest.json" not in cloud
    assert job.REMOTE+"/manifests/manifest-123456788.json" in cloud


def test_immutable_manifest_corruption_does_not_replace_prior(tmp_path,monkeypatch):
    monkeypatch.setattr(job,"command",lambda *a,**k:b"")
    monkeypatch.setattr(job,"read_remote",lambda *a,**k:b"tampered")
    with pytest.raises(RuntimeError,match="readback mismatch"):
        job.publish_manifest(tmp_path,{"file":"snapshot-123456789.sqlite3","sha256":"a"*64},"123456789")
