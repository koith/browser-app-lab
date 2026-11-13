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


def test_bounded_remote_read_times_out_even_before_stdout_eof(monkeypatch):
    # A stalled child keeps stdout open; the old .read(65536) never reached
    # proc.wait(timeout). Use a safe local child, not the real cloud provider.
    import subprocess
    import sys
    import time
    actual_popen=subprocess.Popen
    children=[]
    def stalled(_args,**kwargs):
        proc=actual_popen([sys.executable,"-c",
                           "import time; time.sleep(3)"],**kwargs)
        children.append(proc)
        return proc
    monkeypatch.setattr(job.subprocess,"Popen",stalled)
    started=time.monotonic()
    with pytest.raises(RuntimeError,match="private remote read timed out"):
        job.read_remote("private-synthetic-only",4096,max_seconds=0.08)
    assert time.monotonic()-started<1.5
    assert len(children)==1 and children[0].poll() is not None


def test_bounded_remote_read_preserves_exact_bytes_and_size_limit(monkeypatch):
    import subprocess
    import sys
    actual_popen=subprocess.Popen
    payload=b"safe synthetic original bytes"
    def process(_args,**kwargs):
        return actual_popen([sys.executable,"-c",
                             "import sys; sys.stdout.buffer.write("+
                             repr(payload)+")"],**kwargs)
    monkeypatch.setattr(job.subprocess,"Popen",process)
    assert job.read_remote("private-synthetic-only",len(payload),
                           max_seconds=3)==payload
    with pytest.raises(ValueError,match="private remote payload too large"):
        job.read_remote("private-synthetic-only",len(payload)-1,
                        max_seconds=3)



def test_account_index_stage_audit_reports_success_without_private_data(capsys,monkeypatch):
    values=iter([100.0,100.12])
    monkeypatch.setattr(job.time,"monotonic",lambda:next(values))
    with job.audit_stage("manifest_lookup"):
        pass
    output=capsys.readouterr().out
    assert output.count("PRIVATE_ACCOUNT_INDEX_STAGE")==2
    assert '"state": "begin"' in output
    assert '"state": "pass"' in output
    assert '"elapsed_ms": 120' in output
    assert "archive:" not in output


def test_account_index_stage_audit_redacts_exception_and_refuses_unknown_stage(capsys):
    marker="SECRET_ACCOUNT_POST_AND_PROVIDER_URL_DO_NOT_PRINT"
    with pytest.raises(RuntimeError,match="SECRET_ACCOUNT"):
        with job.audit_stage("catalog_read"):
            raise RuntimeError(marker)
    output=capsys.readouterr().out
    assert '"state": "failed"' in output
    assert marker not in output
    assert output.count("PRIVATE_ACCOUNT_INDEX_STAGE")==2
    with pytest.raises(ValueError,match="unsupported"):
        with job.audit_stage("account@private.example"):
            pass
    assert capsys.readouterr().out==""



def test_catalog_reader_timeout_preserves_checkpoint_budget(tmp_path):
    # The real private backend may require up to 150s for a single SHA-read.
    # Retain an explicit finite worker cap beneath the parent 780s budget.
    assert job.catalog_sync_bounded.__kwdefaults__["timeout_seconds"] == 180
    import sys
    import time
    start=time.monotonic()
    code=job.catalog_sync_bounded(
        str(tmp_path/"accounts.sqlite3"),tmp_path,timeout_seconds=0.08,
        worker=[sys.executable,"-c","import time; time.sleep(4)"])
    assert code=="deferred_timeout"
    assert time.monotonic()-start<2.0
    assert not (tmp_path/"catalog-sync-result.json").exists()


def test_catalog_reader_success_requires_bounded_verified_receipt(tmp_path):
    import sys
    marker=tmp_path/"catalog-sync-result.json"
    script=("import pathlib,sys;pathlib.Path(sys.argv[1]).write_text("
            "chr(123)+'\\\"accepted\\\": 2, \\\"has_posts\\\": true'+chr(125))")
    assert job.catalog_sync_bounded(
        tmp_path/"accounts.sqlite3",tmp_path,timeout_seconds=4,
        worker=[sys.executable,"-c",script,str(marker)])=="verified_2"
    assert marker.exists()


def test_catalog_reader_never_claims_verified_without_receipt(tmp_path):
    import sys
    assert job.catalog_sync_bounded(
        tmp_path/"accounts.sqlite3",tmp_path,timeout_seconds=4,
        worker=[sys.executable,"-c","pass"])=="deferred_invalid_receipt"


def test_catalog_worker_requires_private_cloud_config(tmp_path,monkeypatch):
    monkeypatch.delenv("RCLONE_CONFIG_ARCHIVE_COOKIE",raising=False)
    with pytest.raises(RuntimeError,match="credential"):
        job.catalog_sync_child(tmp_path/"accounts.sqlite3",tmp_path/"catalog-sync-result.json")
    assert not (tmp_path/"catalog-sync-result.json").exists()


def test_direct_manifest_fallback_uses_only_verified_private_candidate():
    import json
    run_id=42445680007
    seen=[]
    def source(path,cap,*,optional,max_seconds):
        seen.append((path,cap,optional,max_seconds))
        return json.dumps({"file":"snapshot-"+str(run_id)+".sqlite3",
                           "sha256":"c"*64}).encode()
    found=job.latest_manifest_from_public_actions(
        get_runs=lambda:{"workflow_runs":[
            {"id":run_id,"head_branch":"main","conclusion":"failure"}]},
        remote_reader=source)
    assert found["file"]=="snapshot-42445680007.sqlite3"
    assert found["sha256"]=="c"*64
    assert len(seen)==1 and seen[0][1:]==(4096,True,14)
    assert seen[0][0].endswith("/manifests/manifest-42445680007.json")


def test_direct_manifest_fallback_rejects_untrusted_branch_and_mismatched_file():
    import json
    calls=[]
    def source(path,cap,*,optional,max_seconds):
        calls.append(path)
        return json.dumps({"file":"snapshot-123456789.sqlite3",
                           "sha256":"c"*64}).encode()
    result=job.latest_manifest_from_public_actions(
        get_runs=lambda:{"workflow_runs":[
            {"id":42445680007,"head_branch":"attacker-branch"},
            {"id":42445680008,"head_branch":"main"}]},
        remote_reader=source)
    assert result is None
    assert len(calls)==1


def test_verified_journal_pages_commit_progress_across_multiple_runs_without_deletion(
        tmp_path,monkeypatch,capsys):
    from test_demand_archive import FakeCloud,post as make_post
    from demand_archive import canonical_json,sha256
    monkeypatch.setenv("RCLONE_CONFIG_ARCHIVE_COOKIE","synthetic-private-test")
    cloud=FakeCloud()
    base=make_post()
    for i in range(3):
        row={**base,"id":str(i+1)*40,
             "source_url":"https://bsky.app/profile/did:plc:abcdefghijk/post/qa"+str(i)}
        cloud.save_post(row)
    db=tmp_path/"private.sqlite3"
    marker=tmp_path/"journal.json"
    totals=[]
    for _ in range(3):
        job.catalog_sync_child(db,marker,cloud=cloud,max_items=1,max_seconds=120)
        receipt=json.loads(marker.read_text())
        assert receipt["mode"]=="journal_incremental"
        assert receipt["verified"]==1
        totals.append(account_index.status(str(db))["source_rows"])
    assert totals==[1,2,3]
    assert account_index.status(str(db))["last_catalog_sync"]==0,(
        "partial journal cannot fake a complete versioned catalog")
    assert receipt["pending"]==0
    # The same old original cannot be erased when a future page is empty.
    job.catalog_sync_child(db,marker,cloud=cloud,max_items=1,max_seconds=120)
    assert account_index.status(str(db))["source_rows"]==3
    assert "https://bsky.app" not in capsys.readouterr().out


def test_broken_remote_post_sha_never_imports_or_replaces_other_originals(
        tmp_path,monkeypatch):
    from test_demand_archive import FakeCloud,post as make_post
    monkeypatch.setenv("RCLONE_CONFIG_ARCHIVE_COOKIE","synthetic-private-test")
    cloud=FakeCloud()
    good={**make_post(),"id":"a"*40}
    bad={**make_post(),"id":"b"*40}
    cloud.save_post(good)
    cloud.save_post(bad)
    db=tmp_path/"archive.sqlite3"
    out=tmp_path/"receipt.json"
    job.catalog_sync_child(db,out,cloud=cloud,max_items=1)
    cloud.objects["posts/"+"b"*40+"/post.json"]=b"tampered-bad-original"
    job.catalog_sync_child(db,out,cloud=cloud,max_items=1)
    body=json.loads(out.read_text())
    assert body["pending"]==1
    assert body["verified"]==0
    assert account_index.status(str(db))["source_rows"]==1
    assert "tampered-bad-original" not in out.read_text()


def test_incremental_receipt_cannot_pass_full_catalog_verified_gate(tmp_path):
    import sys
    marker=tmp_path/"catalog-sync-result.json"
    receipt=json.dumps({"accepted":2,"has_posts":True,
                        "mode":"journal_incremental",
                        "pending":8,"verified":2})
    script="import pathlib,sys;pathlib.Path(sys.argv[1]).write_text("+repr(receipt)+")"
    verdict=job.catalog_sync_bounded(
        str(tmp_path/"archive.sqlite3"),tmp_path,timeout_seconds=4,
        worker=[sys.executable,"-c",script,str(marker)])
    assert verdict=="deferred_journal_pending_8_sha_2_imported_2"
    assert not verdict.startswith("verified_")
