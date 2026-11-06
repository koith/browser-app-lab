#!/usr/bin/env python3
"""Synthetic-only private B2 mirror safety tests. No real upload or credentials."""
import json
import os
from pathlib import Path
import tempfile
from unittest.mock import patch,MagicMock
from importlib.util import spec_from_file_location,module_from_spec

path=Path(__file__).with_name("backfill_private_owner_replica.py")
spec=spec_from_file_location("owner_mirror_backfill",path)
module=module_from_spec(spec)
spec.loader.exec_module(module)

def sample(model,number=1,sha="f"*64):
    return {"schema_version":1,"model":model,
            "albums":[{"id":"verified-owner-work","images":[{
              "number":number,
              "key":f"originals/verified-owner-work/{number:05d}.jpg",
              "sha256":sha,"bytes":1000,"width":400,"height":500}]}]}
with tempfile.TemporaryDirectory() as td:
    root=Path(td)
    for model in ("mimmi","yui"):
        folder=root/(model+"-gallery")
        folder.mkdir()
        data=sample(model)
        (folder/"owner-index.json").write_text(json.dumps(data))
        with patch.object(module,"ROOT",root):
            rows=module.planned_rows(model,data)
            assert len(rows)==1 and rows[0][1]["number"]==1
            wrong=sample(model,sha="a"*64)
            try:module.planned_rows(model,wrong)
            except RuntimeError:pass
            else:raise AssertionError("Wrong owner SHA accepted into private mirror")
    print("OWNER_DURABLE_MIRROR_CATALOG_FINGERPRINT_CLOSED_PASS")
    # Every verified preview must be copied too: otherwise the gallery's
    # normal thumbnail path still 503s even when original backup succeeds.
    one=sample("mimmi")
    one_photo=one["albums"][0]["images"][0]
    one_photo["preview"]="previews/verified-owner-work/00001.jpg"
    one_photo["preview_sha256"]="e"*64
    one_photo["preview_bytes"]=420
    items=module.original_and_preview_variants("mimmi",one["albums"][0],one_photo)
    assert [item[0] for item in items]==["original","preview"]
    assert module.source_manifest_budget("mimmi",[(one["albums"][0],one_photo)])==(2,1420)
    try:
        module.source_manifest_budget("mimmi",[(one["albums"][0],one_photo)],limit_bytes=1419)
    except RuntimeError:pass
    else:raise AssertionError("Preview overflow was accepted as free")
    one_photo["preview"]="previews/other-owner/00001.jpg"
    try:module.original_and_preview_variants("mimmi",one["albums"][0],one_photo)
    except RuntimeError:pass
    else:raise AssertionError("Wrong album preview path accepted")
    print("OWNER_DURABLE_PREVIEW_SHA_PATH_AND_FREE_BYTE_BUDGET_PASS")


env={
 "OWNER_REPLICA_BUCKET":"gallery-private-owner-test",
 "OWNER_DURABLE_REMOTE":"ownerreplica:gallery-private-owner-test",
 "OWNER_REPLICA_PROVIDER":"backblaze-b2",
 "RCLONE_CONFIG_OWNERREPLICA_TYPE":"s3",
 "RCLONE_CONFIG_OWNERREPLICA_PROVIDER":"Other",
 "RCLONE_CONFIG_OWNERREPLICA_ACCESS_KEY_ID":"synthetic-access-key",
 "RCLONE_CONFIG_OWNERREPLICA_SECRET_ACCESS_KEY":"synthetic-secret-key",
 "RCLONE_CONFIG_OWNERREPLICA_ENDPOINT":"https://s3.us-west-004.backblazeb2.com",
 "RCLONE_CONFIG_OWNERREPLICA_REGION":"us-west-004",
}
private={"Grants":[{"Grantee":{"Type":"CanonicalUser","ID":"synthetic-account"},
                   "Permission":"FULL_CONTROL"}]}
public={"Grants":private["Grants"]+[{"Grantee":{
    "Type":"Group","URI":"http://acs.amazonaws.com/groups/global/AllUsers"},
    "Permission":"READ"}]}
with patch.dict(os.environ,env,clear=False):
    with patch.object(module.boto3,"client") as factory:
        factory.return_value.get_bucket_acl.return_value=private
        assert module.require_private_bucket()=="ownerreplica:gallery-private-owner-test"
        factory.return_value.get_bucket_acl.return_value=public
        try:module.require_private_bucket()
        except RuntimeError:pass
        else:raise AssertionError("Public bucket was accepted for plaintext owner images")
    with patch.dict(os.environ,{"OWNER_DURABLE_REMOTE":"ownerreplica:unexpected-bucket"}):
        try:module.credentials()
        except RuntimeError:pass
        else:raise AssertionError("Bucket/key prefix mismatch was accepted")
print("OWNER_DURABLE_ONLY_PRIVATE_B2_BUCKET_CAN_RECEIVE_ORIGINALS_PASS")

# Existing identical files may be skipped; wrong remote byte SHA must abort
# BEFORE upload. No rclone process is ever spawned in this test.
with patch.object(module,"verify_remotely",return_value=True) as verifier:
    did_upload=module.save_immutable("ownerreplica:private/mimmi",
             "originals/verified-owner-work/00001.jpg",b"synthetic", "0"*64)
    assert did_upload is False
    assert verifier.call_count==1
print("OWNER_DURABLE_IMMUTABLE_EXISTING_SHA_SKIP_PASS")

from botocore.exceptions import ClientError
import io
from hashlib import sha256

config={"bucket":"gallery-private-owner-test","region":"us-west-004",
        "endpoint":"https://s3.us-west-004.backblazeb2.com",
        "key":"synthetic-access-key","secret":"synthetic-secret-key"}
new=sample("mimmi")
new["albums"][0]["images"].append({
    "number":2,"key":"originals/verified-owner-work/00002.jpg",
    "sha256":"e"*64,"bytes":500,"width":320,"height":400})
raw=json.dumps(new).encode()
old=sample("mimmi")
oldraw=json.dumps(old).encode()

def fakes(existing):
    client=MagicMock()
    if existing is None:
        client.get_object.side_effect=ClientError(
            {"Error":{"Code":"NoSuchKey","Message":"not found"}},"GetObject")
    else:
        client.get_object.return_value={
            "Body":io.BytesIO(json.dumps(existing).encode()),
            "ETag":'"mock-previous-etag"'}
    return client

with patch.object(module,"credentials",return_value=config),patch.object(
        module,"save_immutable",return_value=True) as saved,patch.object(
        module,"verify_remotely",return_value=True) as readback,patch.object(
        module.boto3,"client") as factory:
    empty=fakes(None);factory.return_value=empty
    assert module.publish_versioned_catalog_only_after_all_sha(
        "mimmi",raw,new,"ownerreplica:bucket/mimmi") is True
    assert empty.put_object.call_args.kwargs["IfNoneMatch"]=="*"
    assert "IfMatch" not in empty.put_object.call_args.kwargs
    assert saved.call_args.args[1]=="metadata/versions/"+sha256(raw).hexdigest()+".json"

    prior=fakes(old);factory.return_value=prior
    assert module.publish_versioned_catalog_only_after_all_sha(
        "mimmi",raw,new,"ownerreplica:bucket/mimmi") is True
    assert prior.put_object.call_args.kwargs["IfMatch"]=='"mock-previous-etag"'
    assert "IfNoneMatch" not in prior.put_object.call_args.kwargs

    # Revision may only APPEND new SHA records; never remove an original.
    shrink=fakes(new);factory.return_value=shrink
    try:
        module.publish_versioned_catalog_only_after_all_sha(
            "mimmi",oldraw,old,"ownerreplica:bucket/mimmi")
    except RuntimeError:pass
    else:raise AssertionError("New manifest silently removed an old SHA")
    shrink.put_object.assert_not_called()

    wrong_owner=fakes(sample("yui"));factory.return_value=wrong_owner
    try:module.publish_versioned_catalog_only_after_all_sha(
        "mimmi",raw,new,"ownerreplica:bucket/mimmi")
    except RuntimeError:pass
    else:raise AssertionError("Foreign owner manifest was accepted")
    wrong_owner.put_object.assert_not_called()
print("OWNER_DURABLE_ATOMIC_VERSIONED_CATALOG_NO_LOST_SHA_PASS")

print("OWNER_DURABLE_APPEND_ONLY_SHA_PILOT_TESTS_PASS")
