#!/usr/bin/env python3
"""Offline smoke for Render Free owner wake probe, with no credentials."""
import io
import json
from pathlib import Path
import sys
from unittest.mock import patch
from urllib.error import URLError
sys.path.insert(0,str(Path(__file__).resolve().parent))
import probe_both_owner_runtime_ready as probe


class Reply(io.BytesIO):
    def __init__(self,payload,status=200,mime="application/json"):
        if not isinstance(payload,bytes):
            payload=json.dumps(payload).encode()
        super().__init__(payload)
        self.status=status
        self.headers={"Content-Type":mime}


def warm():
    return [
        Reply({"service":"Mimmi private archive","data_connected":True}),
        Reply({"albums":[{"id":"verified-yui-album"}]}),
        Reply(b"\x89PNG",mime="image/png"),
        Reply(b"\xff\xd8\xff",mime="image/jpeg")
    ]


with patch.object(probe,"urlopen",side_effect=warm()) as calls:
    assert probe.check() is True
    assert calls.call_count==4
    all_urls=[call.args[0].full_url for call in calls.call_args_list]
    assert all_urls[0].endswith("/api/health")
    assert all_urls[1].endswith("/api/yui/catalog")
    assert all("/api/cover/" in url for url in all_urls[2:])

for replies in [
    [Reply({"data_connected":False})],
    [Reply({"data_connected":True}),Reply({"albums":[]})],
    [Reply({"data_connected":True}),Reply({"albums":[1]}),Reply(b"denied",status=503)],
    [Reply({"data_connected":True}),Reply({"albums":[1]}),Reply(b"{}",mime="application/json")],
    [Reply({"data_connected":True}),Reply({"albums":[1]}),Reply(b"",mime="image/png")],
]:
    with patch.object(probe,"urlopen",side_effect=replies):
        assert probe.check() is False, "Never claim readiness based on incomplete or provider error responses"

with patch.object(probe,"urlopen",side_effect=URLError("Render free sleeping")):
    assert probe.check() is False

print("GALLERY_FREE_RENDER_OWNER_HEARTBEAT_FAIL_CLOSED_OFFLINE_PASS")
