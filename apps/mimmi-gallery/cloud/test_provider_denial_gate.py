#!/usr/bin/env python3
"""Provider access control is respected and not retried in an unbounded storm."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
from gateway.provider_denial_gate import ProviderDenialGate, ProviderAccessHeld

clock=[100.0]
gate=ProviderDenialGate(seconds=25,now=lambda:clock[0])
remote_a='archive:YuiArchive'
remote_b='archive:MimmiArchive'
gate.guard(remote_a)
assert not gate.record(remote_a,'HTTP 403 wrong password')
assert not gate.record(remote_a,'{"error_code":400141}')
gate.guard(remote_a)
raw='HTTP error 403 (403 Forbidden): {"error_code":31326,"error_msg":"anti hotlinking"}'
assert gate.record(remote_a,raw)
try:
    gate.guard(remote_a)
    raise AssertionError("provider denial did not fail closed")
except ProviderAccessHeld as error:
    assert error.retry_seconds==25
gate.guard(remote_b)  # One account path must never block another owner remote.
clock[0]+=12
try:
    gate.guard(remote_a)
    raise AssertionError("provider denial expired early")
except ProviderAccessHeld as error:
    assert error.retry_seconds==13
clock[0]+=14
gate.guard(remote_a)  # Automatically recovers after bounded interval.
assert gate.record(remote_a,'anti-hotlinking'), 'Alternative spelling remains a denial'
gate.success(remote_a)
gate.guard(remote_a)  # A verified good read clears only this gate.
assert not gate.record(remote_b,'i/o timeout: upstream closed connection')
gate.guard(remote_b)
try:
    ProviderDenialGate(seconds=3600)
    raise AssertionError("unbounded denial gate accepted")
except ValueError:
    pass
print('GALLERY_PROVIDER_403_ANTI_HOTLINK_DENIAL_FAIL_CLOSED_AND_RECOVERY_PASS')
