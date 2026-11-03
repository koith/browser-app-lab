"""Credential-free recovery batch tests: original ciphertext and cloud SHA."""
from io import BytesIO
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
    assert key.startswith("metadata/recovery-pack-")
    assert key.endswith(".zip")
    raw=cloud.objects[key]
    digest=hashlib.sha256(raw).hexdigest()
    assert key=="metadata/recovery-pack-"+digest+".zip"
    assert cloud.read_verified(key,digest,cap=len(raw)+1)==raw
    assert b"PRIVATE TEST BODY" not in raw
    assert b"bsky.app" not in raw
    assert b"synthetic-" not in raw
    with zipfile.ZipFile(BytesIO(raw)) as saved:
        assert set(saved.namelist())=={p.name for p in paths}
        for p in paths:
            assert saved.read(p.name)==p.read_bytes()
    assert replay.preserve_encrypted_batch(cloud,spool,paths)==key
    assert len([k for k in cloud.objects if k.startswith("metadata/recovery-pack-")])==1


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
            if key.startswith("metadata/recovery-pack-"):
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
    assert list(cloud.objects)[0].startswith("metadata/recovery-pack-")


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
    assert result["deferred_buffers"]==2
    assert len([x for x in cloud.objects if x.startswith("metadata/recovery-pack-")])==1
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
    monkeypatch.setattr(replay.time,"monotonic",lambda:next(ticks))
    result=replay.replay(cloud=FakeCloud())
    assert len(calls)==2  # Third archived source remains queued, not lost.
    assert result["deferred_artifacts"]==1
    assert result["post_and_media_verified"]==0
    assert result["batch_sha_verified"]==0
