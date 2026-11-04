#!/usr/bin/env python3
"""No-network sanity for full-gallery 49-original recovery readiness."""
import io
import json
from pathlib import Path
import sys
from unittest.mock import patch
from urllib.error import HTTPError, URLError

sys.path.insert(0,str(Path(__file__).resolve().parent))
import probe_private_owner_runtime as probe


class FakeResponse:
    def __init__(self, status, body):
        self.status=status
        self.body=io.BytesIO(json.dumps(body).encode())
    def __enter__(self): return self
    def __exit__(self,*args): self.body.close()
    def read(self, n=-1): return self.body.read(n)


with patch.object(probe,"urlopen",return_value=FakeResponse(200,
    {"ready":True,"expected":49,"available":49})) as request:
    assert probe.check() is True
    assert request.call_count==1
    assert request.call_args.args[0].full_url.endswith("/api/gallery-media-readiness")

for body in (
    {"ready":True,"expected":49,"available":48},
    {"ready":True,"expected":11,"available":11},
    {"ready":False,"expected":49,"available":49},
    {"ready":"true","expected":49,"available":49},
    {},
):
    with patch.object(probe,"urlopen",return_value=FakeResponse(200,body)):
        assert probe.check() is False,body

with patch.object(probe,"urlopen",side_effect=HTTPError(probe.URL,503,"cold",{},None)):
    assert probe.check() is False
with patch.object(probe,"urlopen",side_effect=URLError("connection failed")):
    assert probe.check() is False
print("OWNER_49_EXACT_ORIGINALS_NO_SECRETS_READY_PROBE_FAIL_CLOSED_PASS")
