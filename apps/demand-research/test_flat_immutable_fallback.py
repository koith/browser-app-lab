"""Credential-free regression coverage of TeraBox immutable shallow failover.

No real accounts, cookies, public post IDs, or originals are accessed.
"""
import pytest
from demand_archive import CloudArchive, canonical_json, sha256
from test_demand_archive import FakeCloud, post


@pytest.fixture(autouse=True)
def no_provider_sleep(monkeypatch):
    monkeypatch.setattr("demand_archive.time.sleep", lambda _: None)


class RejectNestedCloud(FakeCloud):
    """Simulate a cloud account where metadata root works but deep parents fail."""

    def fake(self, args, data=None, timeout=150, allow_missing=False):
        op=args[0]
        target=(args[2] if op=="copyto" else args[1]) if len(args)>1 else ""
        nested=("/posts/" in target or
                "/metadata/entries/" in target or
                "/metadata/entries-repaired/" in target or
                "/metadata/catalogs/" in target or
                "/metadata/manifests/" in target or
                "/metadata/media-parts/" in target)
        # The test preserves authentic missing-path semantics: even the
        # alternate provider cannot resolve fresh nested directory paths.
        if op in ("mkdir","copyto","rcat") and nested:
            raise RuntimeError("private cloud "+op+" failed (missing)")
        if op=="lsf" and nested:
            return None
        return super().fake(args,data=data,timeout=timeout,
                            allow_missing=allow_missing)


def test_flat_shallow_archives_media_post_entry_and_manifest_without_false_success():
    cloud=RejectNestedCloud()
    entry=post()
    media=b"exact synthetic photo bytes - never a production original"
    key="posts/"+entry["id"]+"/media/0001.jpg"
    entry["media"]=[{"key":key,"mime":"image/jpeg","bytes":len(media),
                     "sha256":sha256(media),"remote_verified":True}]
    entry["media_expected"]=1
    entry["media_saved"]=1
    saved=cloud.save_post(entry,[media])
    assert saved==entry
    assert key not in cloud.objects
    flat_media=CloudArchive.flat_storage_key(key)
    flat_post=CloudArchive.flat_storage_key("posts/"+entry["id"]+"/post.json")
    flat_entry="metadata/flat-entry-"+entry["id"]+".json"
    assert cloud.objects[flat_media]==media
    assert cloud.objects[flat_post]==canonical_json(entry)
    assert flat_entry in cloud.objects
    assert cloud.read_verified(key,sha256(media),cap=len(media)+1)==media
    assert cloud.names("metadata/entries")==[entry["id"]+".json"]
    assert cloud.load_catalog()==[entry]

    cloud.publish_catalog({entry["id"]:entry},"123456789")
    assert "metadata/flat-manifest-123456789.json" in cloud.objects
    fresh=RejectNestedCloud()
    fresh.objects=cloud.objects
    assert fresh.load_catalog(include_entries=False)==[entry]
    assert fresh.load_catalog()==[entry]
    assert fresh.read_verified(key,sha256(media),cap=len(media)+1)==media
    assert not any(k.startswith("posts/") for k in fresh.objects)


def test_first_observation_fallback_reuses_discoverable_early_marker():
    cloud=RejectNestedCloud()
    entry=post()
    capture=canonical_json({"id":entry["id"],"text":"synthetic"})
    assert cloud.save_first_observation(entry["id"],capture)==capture
    assert cloud.objects["metadata/early-"+entry["id"]+".json"]==capture
    another=RejectNestedCloud()
    another.objects=cloud.objects
    assert entry["id"] in another.pending_capture_ids({})
    assert another.read_first_observation(entry["id"])==capture


def test_canonical_conflicting_original_is_never_overwritten_or_shadowed():
    cloud=RejectNestedCloud()
    entry=post()
    key="posts/"+entry["id"]+"/post.json"
    cloud.objects[key]=b"preexisting immutable source bytes"
    with pytest.raises(RuntimeError,match="immutable archive key collision"):
        cloud.write_immutable(key,b"different source bytes")
    assert cloud.objects[key]==b"preexisting immutable source bytes"
    assert CloudArchive.flat_storage_key(key) not in cloud.objects


def test_authorization_failure_is_not_bypassed_via_shallow_path():
    class Denied(RejectNestedCloud):
        def fake(self,args,data=None,timeout=150,allow_missing=False):
            if args[0]=="mkdir" and "/posts/" in args[1]:
                raise RuntimeError("private cloud mkdir failed (authorization)")
            return super().fake(args,data=data,timeout=timeout,
                                allow_missing=allow_missing)
    cloud=Denied()
    with pytest.raises(RuntimeError,match="authorization"):
        cloud.save_post(post())
    assert cloud.objects=={}


def test_corrupt_flat_original_does_not_count_as_verified():
    cloud=RejectNestedCloud()
    entry=post()
    cloud.save_post(entry)
    key="posts/"+entry["id"]+"/post.json"
    flat=CloudArchive.flat_storage_key(key)
    expected=sha256(canonical_json(entry))
    cloud.objects[flat]=b"corrupted synthetic content"
    assert cloud.read_verified(key,expected)==None
    assert cloud.load_catalog()==[]


def test_normal_canonical_upload_remains_original_contract():
    cloud=FakeCloud()
    entry=post()
    cloud.save_post(entry)
    assert "posts/"+entry["id"]+"/post.json" in cloud.objects
    assert not any(k.startswith("metadata/flat-") for k in cloud.objects)
    assert cloud.load_catalog()==[entry]


def test_total_provider_outage_remains_failure_and_never_creates_marker():
    class Unavailable(RejectNestedCloud):
        def fake(self,args,data=None,timeout=150,allow_missing=False):
            target=(args[2] if args[0]=="copyto" else args[1]) if len(args)>1 else ""
            if ("/metadata" in target and args[0] in ("mkdir","copyto","rcat")):
                raise RuntimeError("private cloud "+args[0]+" failed (missing)")
            if args[0]=="lsf" and "/metadata" in target:
                return None
            return super().fake(args,data=data,timeout=timeout,allow_missing=allow_missing)
    cloud=Unavailable()
    with pytest.raises(RuntimeError):
        cloud.save_post(post())
    assert cloud.objects=={}


def test_replay_opt_in_writes_media_and_journal_shallow_first(monkeypatch):
    monkeypatch.setenv("DEMAND_RECOVERY_PREFER_FLAT","1")
    class Observe(RejectNestedCloud):
        def __init__(self):
            self.mutated=[]
            super().__init__()
        def fake(self,args,data=None,timeout=150,allow_missing=False):
            if args[0] in ("mkdir","copyto","rcat"):
                target=args[2] if args[0]=="copyto" else args[1]
                self.mutated.append(target)
            return super().fake(args,data=data,timeout=timeout,allow_missing=allow_missing)
    cloud=Observe()
    entry=post()
    media=b"synthetic source photo"
    media_key="posts/"+entry["id"]+"/media/0001.jpg"
    entry["media"]=[{"key":media_key,"mime":"image/jpeg","bytes":len(media),
                     "sha256":sha256(media),"remote_verified":True}]
    entry["media_expected"]=entry["media_saved"]=1
    assert cloud.save_post(entry,[media])==entry
    assert cloud.load_catalog()==[entry]
    assert cloud.read_verified(media_key,sha256(media),cap=len(media)+1)==media
    assert cloud.mutated
    assert all("/posts/" not in target and "/metadata/entries/" not in target
               for target in cloud.mutated)
    assert any("metadata/flat-blob-" in target for target in cloud.mutated)


def test_replay_opt_in_never_masks_conflicting_canonical_object(monkeypatch):
    monkeypatch.setenv("DEMAND_RECOVERY_PREFER_FLAT","1")
    cloud=FakeCloud()
    key="posts/"+"b"*40+"/post.json"
    original=b"old canonical bytes"
    cloud.objects[key]=original
    with pytest.raises(RuntimeError,match="canonical checksum conflict"):
        cloud.write_immutable(key,b"new conflicting bytes")
    assert cloud.objects=={key:original}


def test_replay_opt_in_reuses_matching_canonical_without_shadow_copy(monkeypatch):
    monkeypatch.setenv("DEMAND_RECOVERY_PREFER_FLAT","1")
    cloud=FakeCloud()
    key="posts/"+"c"*40+"/post.json"
    original=b"same original"
    cloud.objects[key]=original
    assert cloud.write_immutable(key,original) is False
    assert list(cloud.objects)==[key]


def test_replay_opt_in_cannot_claim_saved_when_shallow_unavailable(monkeypatch):
    monkeypatch.setenv("DEMAND_RECOVERY_PREFER_FLAT","1")
    class Down(FakeCloud):
        def fake(self,args,data=None,timeout=150,allow_missing=False):
            if args[0] in ("copyto","rcat"):
                raise RuntimeError("private cloud "+args[0]+" failed (missing)")
            return super().fake(args,data=data,timeout=timeout,
                                allow_missing=allow_missing)
    cloud=Down()
    with pytest.raises(RuntimeError):
        cloud.save_post(post())
    assert cloud.objects=={}
