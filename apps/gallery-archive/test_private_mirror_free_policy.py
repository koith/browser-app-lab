#!/usr/bin/env python3
"""Synthetic-only free budget and private R2 public-domain guard tests."""
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
import json
import os
from private_mirror_free_policy import (
 PolicyRefusal,check_existing_owner_budget,validated_private_config,
 require_cloudflare_private_standard
)

def make_index(root,model,count,bytes_per=1000):
    p=root/(model+"-gallery")
    p.mkdir(exist_ok=True)
    data={"model":model,"albums":[{"id":"original-owner-work",
      "images":[{"number":i+1,"sha256":f"{i+1:064x}",
          "bytes":bytes_per} for i in range(count)]}]}
    (p/"owner-index.json").write_text(json.dumps(data))
    return data

with TemporaryDirectory() as tmp:
    root=Path(tmp)
    make_index(root,"mimmi",3)
    make_index(root,"yui",2)
    plan=check_existing_owner_budget(root)
    assert plan["objects"]==5 and plan["original_bytes"]==5000
    assert plan["estimated_class_a"]<100_000
    print("FREE_MIRROR_ALL_MODELS_SHA_INVENTORY_BUDGET_PASS")
    make_index(root,"mimmi",65,130_000_000)
    try:check_existing_owner_budget(root)
    except PolicyRefusal:pass
    else:raise AssertionError("Oversized monthly storage budget accepted")
    print("FREE_MIRROR_OVERSIZED_STORAGE_REFUSED_BEFORE_NETWORK_PASS")
    bad=make_index(root,"mimmi",2)
    bad["albums"][0]["images"][1]["number"]=1
    (root/"mimmi-gallery"/"owner-index.json").write_text(json.dumps(bad))
    try:check_existing_owner_budget(root)
    except PolicyRefusal:pass
    else:raise AssertionError("Duplicate owner index accepted")
    print("FREE_MIRROR_DUPLICATE_PRIVATE_OBJECT_REFUSED_PASS")

account="a"*32
env={
 "OWNER_REPLICA_PROVIDER":"cloudflare-r2",
 "OWNER_REPLICA_BUCKET":"strictly-private-gallery-test",
 "OWNER_DURABLE_REMOTE":"ownerreplica:strictly-private-gallery-test",
 "RCLONE_CONFIG_OWNERREPLICA_TYPE":"s3",
 "RCLONE_CONFIG_OWNERREPLICA_PROVIDER":"Cloudflare",
 "RCLONE_CONFIG_OWNERREPLICA_ACCESS_KEY_ID":"synthetic-r2-key",
 "RCLONE_CONFIG_OWNERREPLICA_SECRET_ACCESS_KEY":"synthetic-r2-secret",
 "RCLONE_CONFIG_OWNERREPLICA_ENDPOINT":"https://"+account+".r2.cloudflarestorage.com",
 "RCLONE_CONFIG_OWNERREPLICA_REGION":"auto",
 "OWNER_REPLICA_CF_ACCOUNT_ID":account,
 "OWNER_REPLICA_CF_AUDIT_TOKEN":"synthetic-r2-read-only-audit-token",
}
class Response:
    status=200
    def __init__(self,body):self.body=body
    def __enter__(self):return self
    def __exit__(self,*args):return False
    def read(self,max_bytes):return json.dumps({"success":True,"result":self.body}).encode()

def response_for(path,public=False,cold=False):
    if path.endswith("/domains/managed"):
        return Response({"enabled":public,"bucketId":"synthetic"})
    if path.endswith("/domains/custom"):
        return Response({"domains":[{"domain":"public.example","enabled":True}] if public else []})
    return Response({"name":env["OWNER_REPLICA_BUCKET"],
                     "storage_class":"InfrequentAccess" if cold else "Standard"})

def fake_open(req,timeout):
    assert req.get_header("Authorization")=="Bearer "+env["OWNER_REPLICA_CF_AUDIT_TOKEN"]
    assert req.get_method()=="GET" and timeout==15
    assert req.full_url.startswith("https://api.cloudflare.com/client/v4/accounts/"+account)
    return response_for(req.full_url)

with patch.dict(os.environ,env):
    cfg=validated_private_config()
    assert cfg["provider"]=="cloudflare-r2"
    assert require_cloudflare_private_standard(cfg,opener=fake_open)==cfg["remote"]
    print("FREE_R2_STANDARD_PRIVATE_MANAGED_AND_CUSTOM_DOMAIN_AUDIT_PASS")
    def public_open(req,timeout):return response_for(req.full_url,public=True)
    try:require_cloudflare_private_standard(cfg,opener=public_open)
    except PolicyRefusal:pass
    else:raise AssertionError("Public R2 bucket accepted for private owner image")
    print("FREE_R2_ANY_PUBLIC_DOMAIN_REFUSED_PASS")
    def cold_open(req,timeout):return response_for(req.full_url,cold=True)
    try:require_cloudflare_private_standard(cfg,opener=cold_open)
    except PolicyRefusal:pass
    else:raise AssertionError("Nonfree R2 storage class accepted")
    print("FREE_R2_INFREQUENT_ACCESS_REFUSED_PASS")
    with patch.dict(os.environ,{"RCLONE_CONFIG_OWNERREPLICA_ENDPOINT":"https://other.invalid"}):
        try:validated_private_config()
        except PolicyRefusal:pass
        else:raise AssertionError("Unexpected R2 endpoint accepted")
    print("FREE_R2_ONLY_OWNER_ACCOUNT_ENDPOINT_ACCEPTED_PASS")
