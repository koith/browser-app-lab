#!/usr/bin/env python3
"""Zero-network proof that only same-owner transient failures retry."""
import hashlib
import tempfile
import sys
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parent))
import restore_known_owner_cache as rescue
from qa_existing_owner_exact_file import read_existing
from subprocess import CompletedProcess

def transient_then_ok(remote,key,destination,env):
    attempts.append((remote,key))
    if len(attempts)<3:return False,"remote_read_rejected"
    destination.write_bytes(b"existing exact owner bytes")
    return True,"cat"
attempts=[]
with patch.object(rescue,"read_existing",side_effect=transient_then_ok),patch.object(
        rescue.time,"sleep") as sleep:
    payload=rescue.verified_file("archive:YuiArchive","originals/teddy-bear97/00084.jpg",{},1000)
    assert payload==b"existing exact owner bytes"
    assert len(attempts)==3
    assert len(set(attempts))==1
    assert [c.args[0] for c in sleep.call_args_list]==[7,20]
print("OWNER_SAME_ACCOUNT_TRANSIENT_COOLDOWN_RECOVERY_PASS")

for rejected in ("provider_access_denied","provider_access_rejected",
                 "owner_object_not_found"):
    with patch.object(rescue,"read_existing",return_value=(False,rejected)) as read,patch.object(
            rescue.time,"sleep") as sleep:
        try:
            rescue.verified_file("archive:MimmiArchive","originals/work/00044.jpg",{},1000)
        except rescue.OwnerReadUnavailable:pass
        else:raise AssertionError("Explicit denial was retried or accepted")
        assert read.call_count==1 and sleep.call_count==0,rejected
print("OWNER_EXPLICIT_DENIAL_NO_RETRY_PASS")

def mock_process(argv,**kwargs):
    return CompletedProcess(argv,1,stderr=b'ERROR: HTTP error 403: Forbidden')
with tempfile.TemporaryDirectory() as folder,patch(
        "qa_existing_owner_exact_file.subprocess.run",side_effect=mock_process) as proc:
    ok,reason=read_existing("archive:YuiArchive","originals/teddy-bear97/00084.jpg",
                            Path(folder)/"photo",{})
    assert ok is False and reason=="provider_access_denied"
    assert proc.call_count==1
print("OWNER_GENERIC_403_DENIAL_DOES_NOT_BYPASS_PASS")

for stderr,expected in ((b'HTTP error 429 Too Many Requests',"retryable_http_failure"),
                        (b'HTTP error 503 Service Unavailable',"retryable_http_failure"),
                        (b'connection reset by peer',"retryable_transport_failure"),
                        (b'HTTP error 404 Not Found',"owner_object_not_found")):
    def failure(argv,**kwargs):return CompletedProcess(argv,1,stderr=stderr)
    with tempfile.TemporaryDirectory() as folder,patch(
            "qa_existing_owner_exact_file.subprocess.run",side_effect=failure) as proc:
        ok,reason=read_existing("archive:MimmiArchive","originals/work/00044.jpg",
                                Path(folder)/"photo",{})
        assert not ok and reason==expected,(stderr,reason)
        assert proc.call_count==1
print("OWNER_CLASSIFIED_429_5XX_TRANSPORT_AND_MISSING_PASS")
