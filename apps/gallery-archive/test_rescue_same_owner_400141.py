#!/usr/bin/env python3
"""No-network provider-code gating for actual rescue read.
The same authenticated account may use copyto only for documented 400141;
explicit 31326 anti-hotlinking never gets an alternative request.
"""
import os
import sys
from pathlib import Path
from unittest.mock import patch
from subprocess import CompletedProcess

ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT))
import restore_known_owner_cache as rescue
from qa_existing_owner_exact_file import read_existing

def fake_run_factory(code,body):
    calls=[]
    def fake_run(argv,**kwargs):
        calls.append(list(argv))
        if argv[1]=="cat":
            return CompletedProcess(argv,1,stderr=("provider error_code: "+str(code)).encode())
        assert argv[1]=="copyto"
        Path(argv[3]).write_bytes(body)
        return CompletedProcess(argv,0,stderr=b"")
    return calls,fake_run

data=b"existing-owner-verified-photo-bytes"
env={"RCLONE_CONFIG_ARCHIVE_COOKIE":"same-model-owner-test"}
calls,fake=fake_run_factory(400141,data)
with patch("qa_existing_owner_exact_file.subprocess.run",side_effect=fake):
    result=rescue.verified_file("archive:YuiArchive","originals/example/001.jpg",env,1024)
assert result==data
assert [c[1] for c in calls]==["cat","copyto"],calls
assert all(c[2]=="archive:YuiArchive/originals/example/001.jpg" for c in calls)
print("OWNER_RESCUE_400141_SAME_ACCOUNT_COPYTO_PASS")

calls,fake=fake_run_factory(31326,data)
with patch("qa_existing_owner_exact_file.subprocess.run",side_effect=fake):
    try:
        rescue.verified_file("archive:YuiArchive","originals/example/001.jpg",env,1024)
    except rescue.OwnerReadUnavailable:
        pass
    else:
        raise AssertionError("Explicit provider denial must fail")
assert len(calls)==1 and calls[0][1]=="cat"
print("OWNER_RESCUE_31326_PROVIDER_DENIAL_FAIL_CLOSED_PASS")

for key in ("../../secrets","/root","other\\key"):
    calls,fake=fake_run_factory(400141,data)
    with patch("qa_existing_owner_exact_file.subprocess.run",side_effect=fake):
        try:
            rescue.verified_file("archive:MimmiArchive",key,env,1024)
        except rescue.OwnerReadUnavailable:
            pass
        else:
            raise AssertionError("Unsafe path accepted")
    assert not calls
print("OWNER_RESCUE_NO_UNSAFE_PATHS_PASS")
