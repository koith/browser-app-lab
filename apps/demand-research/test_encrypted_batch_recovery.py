"""Credential-free recovery batch tests: original ciphertext and cloud SHA."""
from io import BytesIO
from types import SimpleNamespace
import hashlib
import json
import zipfile

import pytest

import recover_spool_artifacts as replay
from recovery_spool import RecoverySpool
from test_recovery_spool import first
from test_demand_archive import FakeCloud


@pytest.fixture(autouse=True)
def private_synthetic_env(monkeypatch):
    monkeypatch.setenv("DEMAND_ARCHIVE_RECOVERY_KEY",
                       "only-for-tests-long-private-key-not-production")
    monkeypatch.setenv("RCLONE_CONFIG_ARCHIVE_COOKIE",
                       "only-for-tests-not-a-real-terabox-cookie")
    monkeypatch.setenv("GITHUB_REPOSITORY","koith/browser-app-lab")
    monkeypatch.setattr("demand_archive.time.sleep",lambda _:None)


def test_multiple_originals_are_recoverable_from_one_sha_verified_private_batch(tmp_path):
    spool=RecoverySpool(tmp_path)
    paths=[]
    for n in range(3):
        pid=hashlib.sha1(("synthetic-"+str(n)).encode()).hexdigest()
        paths.append(spool.save(pid,first(pid)))
    cloud=FakeCloud()
    key=replay.preserve_encrypted_batch(cloud,spool,paths)
    assert key.startswith("recovery-pack-")
    assert key.endswith(".zip")
    raw=cloud.objects[key]
    digest=hashlib.sha256(raw).hexdigest()
    assert key=="recovery-pack-"+digest+".zip"
    assert cloud.read_verified(key,digest,cap=len(raw)+1)==raw
    assert b"PRIVATE TEST BODY" not in raw
    assert b"bsky.app" not in raw
    assert b"synthetic-" not in raw
    with zipfile.ZipFile(BytesIO(raw)) as saved:
        assert set(saved.namelist())=={p.name for p in paths}
        for p in paths:
            assert saved.read(p.name)==p.read_bytes()
    assert replay.preserve_encrypted_batch(cloud,spool,paths)==key
    assert len([k for k in cloud.objects if k.startswith("recovery-pack-")])==1


def test_tampered_ciphertext_refused_before_cloud_backup(tmp_path):
    spool=RecoverySpool(tmp_path)
    pid="a"*40
    path=spool.save(pid,first(pid))
    raw=path.read_bytes()
    path.write_bytes(raw[:-1]+bytes([raw[-1]^1]))
    cloud=FakeCloud()
    with pytest.raises(ValueError):
        replay.preserve_encrypted_batch(cloud,spool,[path])
    assert cloud.objects=={}


def test_unverified_cloud_readback_never_claims_recovered_private_batch(tmp_path):
    class StaleReadback(FakeCloud):
        def read_verified(self,key,digest,*,cap=1):
            if key.startswith("recovery-pack-"):
                return None
            return super().read_verified(key,digest,cap=cap)
    spool=RecoverySpool(tmp_path)
    pid="b"*40
    path=spool.save(pid,first(pid))
    cloud=StaleReadback()
    with pytest.raises(RuntimeError,match="checksum unverified"):
        replay.preserve_encrypted_batch(cloud,spool,[path])
    assert len(cloud.objects)==1
    # Exists is not the same as independently SHA-verified.
    assert list(cloud.objects)[0].startswith("recovery-pack-")




def test_safe_failure_buckets_use_fixed_codes_not_private_exception_messages():
    """Even secret-bearing provider errors must not leak to Actions summaries."""
    details="private-credential-DO-NOT-LOG remote:/sensitive/filename"
    cases=[
        (TimeoutError(details),"timeout"),
        (RuntimeError("(missing) "+details),"missing_remote_path"),
        (RuntimeError("(authorization) "+details),"authorization"),
        (RuntimeError("(capacity) "+details),"capacity"),
        (RuntimeError("(rate_limited) "+details),"rate_limited"),
        (RuntimeError("checksum mismatch "+details),"integrity_conflict"),
        (RuntimeError("private cloud readback did not converge "+details),"readback_unverified"),
        (ValueError(details),"invalid_record"),
        (RuntimeError(details),"backend_unclassified")
    ]
    for error,expected in cases:
        category=replay.safe_failure_category(error)
        assert category==expected
        assert details not in category
    try:
        try:
            raise RuntimeError("(missing) "+details)
        except RuntimeError as inner:
            raise RuntimeError("private cloud post write unverified") from inner
    except RuntimeError as outer:
        assert replay.safe_failure_category(outer)=="missing_remote_path"
    aggregate={"buffer_error_categories":{}}
    replay.count_safe_failure(aggregate,"buffer_error_categories",RuntimeError(details))
    assert aggregate=={"buffer_error_categories":{"backend_unclassified":1}}
    assert details not in json.dumps(aggregate)


def test_recovery_timeout_is_counted_without_disclosing_source_name(tmp_path,monkeypatch):
    spool=RecoverySpool(tmp_path)
    for i in range(4):
        pid=hashlib.sha1(("timeout-private-"+str(i)).encode()).hexdigest()
        spool.save(pid,first(pid))
    def always_times_out(*args,**kwargs):
        raise TimeoutError("sensitive archived original path should never be printed")
    monkeypatch.setattr(replay,"restore_with_budget",always_times_out)
    result=replay.replay(cloud=FakeCloud(),local_directory=tmp_path)
    assert result["buffer_failures"]==3
    assert result["deferred_buffers"]==1
    assert result["buffer_error_categories"]=={"timeout":3}
    assert "sensitive" not in json.dumps(result)




def test_root_ciphertext_pack_avoids_broken_metadata_directory(
        tmp_path,monkeypatch):
    """Use root for an immutable ciphertext ZIP without trying broken child dirs."""
    class RootOnly(FakeCloud):
        def write_immutable(self,key,data):
            if key.startswith("metadata/recovery-pack-"):
                try:
                    raise RuntimeError("(missing) nested metadata parent")
                except RuntimeError as inner:
                    raise RuntimeError("private cloud write unverified") from inner
            return super().write_immutable(key,data)

        def names(self,prefix):
            if prefix=="":
                return sorted(key for key in self.objects if "/" not in key)
            return super().names(prefix)

    spool=RecoverySpool(tmp_path)
    from test_demand_archive import post as synthetic_post
    from demand_archive import sha256
    record=synthetic_post()
    pid=record["id"]
    observation=first(pid)
    observation["media_links"]=["https://cdn.bsky.app/img/synthetic-root-original.jpg"]
    record.update({"text":observation["text"],"source_url":observation["source_url"],
                   "posted_at":observation["posted_at"],"media_expected":1,
                   "media_saved":1,"archive_complete":True})
    original=b"only-verified-synthetic-original-video-data"
    record["media"]=[{"key":"posts/"+pid+"/media/0001.jpg","mime":"image/jpeg",
                       "bytes":len(original),"sha256":sha256(original),
                       "remote_verified":True}]
    sealed=spool.save(pid,observation,record,[original])
    cloud=RootOnly()
    key=replay.preserve_encrypted_batch(cloud,spool,[sealed])
    assert key.startswith("recovery-pack-") and "/" not in key
    assert b"PRIVATE TEST BODY" not in cloud.objects[key]
    assert b"bsky.app" not in cloud.objects[key]
    assert replay.select_remote_encrypted_packs(cloud)==[key]
    sealed.unlink()  # Simulate short-lived Actions artifact expiry.
    monkeypatch.setenv("GH_TOKEN","offline-test-only")
    monkeypatch.delenv("DEMAND_RECOVERY_SOURCE_RUN_ID",raising=False)
    monkeypatch.setattr(replay,"list_candidates",lambda:[])
    done=replay.replay(cloud=cloud)
    assert done["remote_packs_sha_verified"]==1
    assert done["post_and_media_verified"]==1
    assert done["buffer_failures"]==0
    assert cloud.objects["posts/"+pid+"/media/0001.jpg"]==original
    assert cloud.objects[key],"encrypted immutable pack was not deleted"


def test_integrity_collision_must_not_be_bypassed_by_root_pack_fallback(tmp_path):
    class CollisionCloud(FakeCloud):
        def write_immutable(self,key,data):
            if key.startswith("recovery-pack-"):
                raise RuntimeError("immutable archive key collision: checksum conflict")
            return super().write_immutable(key,data)
    spool=RecoverySpool(tmp_path)
    pid="d"*40
    sealed=spool.save(pid,first(pid))
    cloud=CollisionCloud()
    with pytest.raises(RuntimeError,match="collision"):
        replay.preserve_encrypted_batch(cloud,spool,[sealed])
    assert not any(key.startswith("recovery-pack-") for key in cloud.objects)


def test_missing_root_ciphertext_path_can_use_legacy_metadata(tmp_path):
    """Only a missing root path permits the backward-compatible legacy path."""
    class MetadataOnly(FakeCloud):
        def write_immutable(self,key,data):
            if key.startswith("recovery-pack-"):
                raise RuntimeError("(missing) synthetic root directory unavailable")
            return super().write_immutable(key,data)
    spool=RecoverySpool(tmp_path)
    sealed=spool.save("f"*40,first("f"*40))
    cloud=MetadataOnly()
    key=replay.preserve_encrypted_batch(cloud,spool,[sealed])
    assert key.startswith("metadata/recovery-pack-")
    digest=hashlib.sha256(cloud.objects[key]).hexdigest()
    assert key=="metadata/recovery-pack-"+digest+".zip"
    assert replay.select_remote_encrypted_packs(cloud)==[key]


def test_denied_root_pack_does_not_bypass_authorization(tmp_path):
    class Denied(FakeCloud):
        def write_immutable(self,key,data):
            if key.startswith("recovery-pack-"):
                raise RuntimeError("(authorization) remote refused private storage")
            return super().write_immutable(key,data)
    spool=RecoverySpool(tmp_path)
    sealed=spool.save("e"*40,first("e"*40))
    cloud=Denied()
    with pytest.raises(RuntimeError,match="authorization"):
        replay.preserve_encrypted_batch(cloud,spool,[sealed])
    assert cloud.objects=={}, "authorization denial must not fall back to another path"


def test_backlog_fair_rotation_preserves_oldest_and_changes_other_sources(monkeypatch):
    def fixture_page(args,**kwargs):
        assert args[0]=="api"
        batch=[]
        for k in range(35):
            batch.append({"name":"intersection-private-recovery",
                          "size_in_bytes":100,
                          "expired":False,
                          "created_at":f"2026-11-03T10:{k:02d}:00Z",
                          "workflow_run":{"id":41640000000+k,
                                          "head_branch":"main",
                                          "repository_id":123,
                                          "head_repository_id":123}})
        return json.dumps({"artifacts":batch}).encode()
    monkeypatch.setattr(replay,"_gh",fixture_page)
    monkeypatch.setenv("GITHUB_RUN_ID","41650000000")
    a=replay.list_candidates()
    monkeypatch.setenv("GITHUB_RUN_ID","41650000001")
    b=replay.list_candidates()
    assert len(a)==len(b)==replay.MAX_ARTIFACTS
    assert a[:3]==b[:3]
    assert a[3:]!=b[3:]
    assert all(x[2]=="intersection-private-recovery" for x in a+b)


def test_degraded_capture_keeps_sha_verified_batch_separate_from_post_restore(tmp_path):
    class DownCloud(FakeCloud):
        def save_first_observation(self,*args,**kwargs):
            raise RuntimeError("synthetic provider refusing per-post writes")
    spool=RecoverySpool(tmp_path)
    for n in range(5):
        pid=hashlib.sha1(str(n).encode()).hexdigest()
        spool.save(pid,first(pid))
    cloud=DownCloud()
    result=replay.replay(cloud=cloud,local_directory=tmp_path)
    assert result["batch_sha_verified"]==1
    assert result["batch_ciphertext_count"]==5
    assert result["post_and_media_verified"]==0
    assert result["first_observation_verified"]==0
    assert result["buffer_failures"]==3
    assert result["buffer_error_categories"]=={"backend_unclassified":3}
    assert result["deferred_buffers"]==2
    assert len([x for x in cloud.objects if x.startswith("recovery-pack-")])==1
    assert len(list(tmp_path.glob("*.enc")))==5



def test_recovery_batch_time_limit_interrupts_backend_retry_and_restores_runner(tmp_path):
    spool=RecoverySpool(tmp_path)
    path=spool.save("c"*40,first("c"*40))
    cloud=FakeCloud()
    original_runner=cloud.runner
    with pytest.raises(TimeoutError,match="budget exceeded"):
        replay.with_cloud_budget(
            cloud,lambda:replay.preserve_encrypted_batch(cloud,spool,[path]),
            max_seconds=-1)
    assert cloud.runner is original_runner
    assert cloud.objects=={}


def test_replay_streams_artifacts_and_reports_unprocessed_backlog(monkeypatch):
    """Avoid an Actions timeout even when a backlog has many slow downloads."""
    from test_demand_archive import FakeCloud
    monkeypatch.setenv("GH_TOKEN","synthetic-token-for-tests")
    monkeypatch.setattr(replay,"list_candidates",lambda: [
        ("2026-11-03T00:00:00Z",100001,"intersection-private-recovery"),
        ("2026-11-03T00:01:00Z",100002,"intersection-private-recovery"),
        ("2026-11-03T00:02:00Z",100003,"intersection-private-recovery"),
    ])
    calls=[]
    monkeypatch.setattr(replay,"_gh",
                        lambda args,**kwargs:calls.append(args) or b"")
    ticks=iter([0,300,600,900])
    monkeypatch.setattr(replay,"time",SimpleNamespace(monotonic=lambda:next(ticks)))
    result=replay.replay(cloud=FakeCloud())
    assert len(calls)==2  # Third archived source remains queued, not lost.
    assert result["deferred_artifacts"]==1
    assert result["post_and_media_verified"]==0
    assert result["batch_sha_verified"]==0

def test_expired_github_artifact_restores_exact_post_and_media_from_terabox_pack(
        tmp_path,monkeypatch):
    """The source Actions artifact can disappear; immutable cloud ciphertext
    must still recover exact original SHA-matched media and first observation.
    """
    from demand_archive import sha256,canonical_json
    from test_demand_archive import post as synthetic_post
    monkeypatch.setenv("GH_TOKEN","offline-test-no-real-github-requests")
    monkeypatch.delenv("DEMAND_RECOVERY_SOURCE_RUN_ID",raising=False)
    monkeypatch.setattr(replay,"list_candidates",lambda:[])
    spool=RecoverySpool(tmp_path)
    post=synthetic_post()
    pid=post["id"]
    first_seen=first(pid)
    first_seen["media_links"]=["https://cdn.bsky.app/img/synthetic-only-original.jpg"]
    post.update({"text":first_seen["text"],"source_url":first_seen["source_url"],
                 "posted_at":first_seen["posted_at"],"media_expected":1,
                 "media_saved":1,"archive_complete":True})
    original=b"original synthetic picture exactly preserved 1234567"
    post["media"]=[{"key":"posts/"+pid+"/media/0001.jpg","mime":"image/jpeg",
                    "bytes":len(original),"sha256":sha256(original),
                    "remote_verified":True}]
    sealed=spool.save(pid,first_seen,post,[original])
    cloud=FakeCloud()
    key=replay.preserve_encrypted_batch(cloud,spool,[sealed])
    sealed.unlink()  # Only the TEST'S local Actions artifact is removed.
    assert not list(tmp_path.glob("*.enc"))
    result=replay.replay(cloud=cloud)
    assert result["remote_packs_sha_verified"]==1
    assert result["remote_pack_ciphertext_count"]==1
    assert result["post_and_media_verified"]==1
    assert result["remote_pack_failures"]==0
    assert result["buffer_failures"]==0
    assert cloud.objects["posts/"+pid+"/media/0001.jpg"]==original
    assert cloud.read_first_observation(pid)==canonical_json(first_seen)
    assert cloud.objects[key],"source encrypted pack is never deleted"
    # Idempotent replay: no overwritten immutable original or duplicated data.
    again=replay.replay(cloud=cloud)
    assert again["post_and_media_verified"]==1
    assert cloud.objects["posts/"+pid+"/media/0001.jpg"]==original


def test_sha_mismatch_cloud_pack_never_restores_or_claims_success(
        tmp_path,monkeypatch):
    monkeypatch.setenv("GH_TOKEN","offline-test-no-real-github-requests")
    monkeypatch.delenv("DEMAND_RECOVERY_SOURCE_RUN_ID",raising=False)
    monkeypatch.setattr(replay,"list_candidates",lambda:[])
    cloud=FakeCloud()
    cloud.objects["metadata/recovery-pack-"+("a"*64)+".zip"]=b"invalid"
    result=replay.replay(cloud=cloud)
    assert result["remote_pack_failures"]==1
    assert result["remote_packs_sha_verified"]==0
    assert result["post_and_media_verified"]==0
    assert not any(key.startswith("posts/") for key in cloud.objects)


def test_verified_zip_with_path_traversal_is_refused_before_remote_writes(
        tmp_path):
    cloud=FakeCloud()
    buffer=BytesIO()
    with zipfile.ZipFile(buffer,"w") as out:
        out.writestr("../"+("a"*64)+".enc",b"not encrypted")
    raw=buffer.getvalue()
    key="metadata/recovery-pack-"+hashlib.sha256(raw).hexdigest()+".zip"
    cloud.objects[key]=raw
    with pytest.raises(ValueError,match="unsafe private recovery pack member"):
        replay.extract_verified_remote_pack(cloud,key,tmp_path/"isolated")
    assert not list(tmp_path.rglob("*.enc"))
    assert list(cloud.objects)==[key]


def test_cloud_pack_selection_is_bounded_and_rotates(monkeypatch):
    cloud=FakeCloud()
    for n in range(7):
        cloud.objects["metadata/recovery-pack-"+format(n,"064x")+".zip"]=b"stub"
    cloud.objects["metadata/unrelated-secret.zip"]=b"must-not-read"
    monkeypatch.setenv("GITHUB_RUN_ID","41700010001")
    first_selection=replay.select_remote_encrypted_packs(cloud)
    monkeypatch.setenv("GITHUB_RUN_ID","41700010002")
    second_selection=replay.select_remote_encrypted_packs(cloud)
    assert len(first_selection)==len(second_selection)==replay.MAX_CLOUD_PACKS
    assert first_selection!=second_selection
    assert all(x.startswith("metadata/recovery-pack-") for x in
               first_selection+second_selection)


def test_source_run_targeted_restore_never_scans_other_cloud_packs(
        tmp_path,monkeypatch):
    """An explicitly requested main-branch capture cannot borrow another
    user's unrelated remote batch from the general historical backlog.
    """
    monkeypatch.setenv("GH_TOKEN","offline-test-no-real-github-requests")
    monkeypatch.setenv("DEMAND_RECOVERY_SOURCE_RUN_ID","41700010003")
    monkeypatch.setattr(replay,"validate_source_run",lambda _:True)
    monkeypatch.setattr(replay,"select_remote_encrypted_packs",
                        lambda cloud: (_ for _ in ()).throw(
                            AssertionError("targeted restore must not scan remote packs")))
    monkeypatch.setattr(replay,"_gh",lambda args,**kwargs:b"")
    cloud=FakeCloud()
    result=replay.replay(cloud=cloud)
    assert result["remote_packs_sha_verified"]==0
    assert result["remote_pack_list_failures"]==0



def test_slow_archive_replay_has_finite_stage_aware_backend_budget():
    """Increase slow SHA read allowance without allowing an unbounded request."""
    from types import SimpleNamespace
    observed=[]
    def backend(args,data=None,timeout=0,allow_missing=False):
        observed.append(timeout)
        return b"synthetic"
    cloud=SimpleNamespace(runner=backend)
    assert replay.MAX_RECORD_SECONDS==120
    assert replay.with_cloud_budget(
        cloud,lambda:cloud.runner(["cat","synthetic"],timeout=250),
        max_seconds=replay.MAX_RECORD_SECONDS)==b"synthetic"
    assert 0<observed[0]<=45
    assert cloud.runner is backend


def test_replay_reports_only_safe_first_observation_timeout_stage(tmp_path):
    class SlowCloud(FakeCloud):
        def save_first_observation(self,*args,**kwargs):
            raise TimeoutError("private account identifier SHOULD NEVER LEAK")
    spool=RecoverySpool(tmp_path)
    spool.save("a"*40,first("a"*40))
    result=replay.replay(cloud=SlowCloud(),local_directory=tmp_path)
    assert result["buffer_failures"]==1
    assert result["buffer_error_categories"]=={"timeout":1}
    assert result["buffer_failure_stages"]=={"first_observation":1}
    assert "SHOULD NEVER LEAK" not in json.dumps(result)


def test_three_bad_first_artifact_buffers_do_not_block_distinct_good_artifact(
        tmp_path,monkeypatch):
    """A broken source ZIP cannot poison the rest of the authorized backlog."""
    from pathlib import Path
    import shutil
    monkeypatch.setenv("GH_TOKEN","synthetic-private-github-token")
    monkeypatch.delenv("DEMAND_RECOVERY_SOURCE_RUN_ID",raising=False)
    first_src=tmp_path/"bad"
    second_src=tmp_path/"good"
    first_spool=RecoverySpool(first_src)
    second_spool=RecoverySpool(second_src)
    blocked=set()
    for n in range(3):
        pid=hashlib.sha1(("bad-artifact-"+str(n)).encode()).hexdigest()
        blocked.add(first_spool.save(pid,first(pid)).name)
    goodpid=hashlib.sha1(b"good-second-artifact").hexdigest()
    good_file=second_spool.save(goodpid,first(goodpid))
    monkeypatch.setattr(replay,"list_candidates",lambda:[
        ("2026-11-01T00:00:00Z",123451,"intersection-private-recovery"),
        ("2026-11-01T01:00:00Z",123452,"intersection-private-recovery")])
    monkeypatch.setattr(replay,"select_remote_encrypted_packs",lambda _cloud:[])
    def fake_download(args,*,max_bytes=2_000_000):
        assert args[:2]==["run","download"]
        source=first_src if args[2]=="123451" else second_src
        dest=Path(args[-1])
        for item in source.glob("*.enc"):
            shutil.copyfile(item,dest/item.name)
        return b""
    monkeypatch.setattr(replay,"_gh",fake_download)
    original=replay.restore_with_budget
    def reject_only_first(spool,path,cloud,**kwargs):
        if path.name in blocked:
            raise TimeoutError("synthetic private failure that must never print")
        return original(spool,path,cloud,**kwargs)
    monkeypatch.setattr(replay,"restore_with_budget",reject_only_first)
    result=replay.replay(cloud=FakeCloud())
    assert result["buffer_failures"]==3
    assert result["first_observation_verified"]==1
    assert result["deferred_artifacts"]==0
    assert result["artifacts"]==2
    assert "synthetic private failure" not in json.dumps(result)
