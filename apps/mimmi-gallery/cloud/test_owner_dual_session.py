#!/usr/bin/env python3
"""Offline model-separated TeraBox session checks: no real credentials/network."""
from __future__ import annotations
import asyncio
import json
import os
from unittest.mock import patch
from fastapi import HTTPException
from fastapi.testclient import TestClient

os.environ.setdefault("GALLERY_ACCESS_TOKEN","offline-test-only")
os.environ.setdefault("RCLONE_CONFIG_ARCHIVE_COOKIE","offline-test-owner")
from gateway import main as gateway


class Reader:
    def __init__(self, data: bytes):
        self.data = data
    async def read(self, n=65536):
        chunk, self.data = self.data[:n], self.data[n:]
        return chunk


class Process:
    returncode = 0
    def __init__(self, data):
        self.stdout = Reader(data)
        self.stderr = Reader(b"")
    async def wait(self):
        return 0
    def kill(self):
        self.returncode = -9


async def test_model_specific_child_process_cookie():
    observed = []
    async def start(*args, **kwargs):
        observed.append((args[2], kwargs["env"]["RCLONE_CONFIG_ARCHIVE_COOKIE"]))
        return Process(b'{"schema_version":1}')
    env = {
        "RCLONE_CONFIG_ARCHIVE_COOKIE": "mimmi-fixture-unique",
        "RCLONE_CONFIG_ARCHIVE_YUI_COOKIE": "yui-fixture-unique",
    }
    with patch.dict(os.environ, env), patch.object(gateway, "cookie_header",
        side_effect=lambda x:x), patch.object(gateway.asyncio,
        "create_subprocess_exec", side_effect=start):
        await gateway.rclone_bytes("metadata/catalog.json", 4096, remote=gateway.REMOTE)
        await gateway.rclone_bytes("metadata/catalog.json", 4096, remote=gateway.YUI_REMOTE)
    assert observed == [
        (gateway.REMOTE + "/metadata/catalog.json", env["RCLONE_CONFIG_ARCHIVE_COOKIE"]),
        (gateway.YUI_REMOTE + "/metadata/catalog.json", env["RCLONE_CONFIG_ARCHIVE_YUI_COOKIE"]),
    ], observed
    print("GALLERY_DUAL_OWNER_SEPARATE_SUBPROCESS_AUTH_PASS")


asyncio.run(test_model_specific_child_process_cookie())


async def simulated_remote(path, limit, *, remote=None, cookie_override=None):
    assert path == "metadata/catalog.json"
    model = "mimmi" if remote == gateway.REMOTE else "yui"
    wanted = model + "-cookie-fixture"
    if cookie_override != wanted:
        raise HTTPException(status_code=503, detail="Simulated incorrect account")
    return json.dumps({
        "schema_version":1, "model":model,
        "albums":[{"id":model+"-work", "images":[{"number":1}]}]
    }).encode()


old_cookie=gateway.COOKIE
old_mimmi=gateway._cache.copy()
old_yui=gateway._yui_cache.copy()
try:
    with patch.dict(os.environ, {
        "RCLONE_CONFIG_ARCHIVE_COOKIE":"prior-mimmi-secret",
        "RCLONE_CONFIG_ARCHIVE_YUI_COOKIE":"prior-yui-secret",
    }), patch.object(gateway, "_verify_sync_identity",
        side_effect=lambda token:token=="offline-OIDC-valid"), patch.object(
            gateway, "rclone_bytes", side_effect=simulated_remote):
        with TestClient(gateway.app) as client:
            endpoint="/internal/terabox-session-refresh"
            header={"Authorization":"Bearer offline-OIDC-valid"}
            assert client.post(endpoint,json={
                "cookie":"mimmi-cookie-fixture","yui_cookie":"yui-cookie-fixture"
            }).json()=={"synced":True,"models":["mimmi","yui"],"unavailable_models":[]}
            assert os.environ["RCLONE_CONFIG_ARCHIVE_COOKIE"]=="mimmi-cookie-fixture"
            assert os.environ["RCLONE_CONFIG_ARCHIVE_YUI_COOKIE"]=="yui-cookie-fixture"
            assert gateway.COOKIE=="mimmi-cookie-fixture"

            # Mimmi rejection must NOT roll back a good Yui session.
            partial=client.post(endpoint,headers=header,json={
                "cookie":"incorrect-mimmi-session","yui_cookie":"yui-cookie-fixture"
            })
            assert partial.status_code==200,partial.text
            assert partial.json()=={
                "synced":False,"models":["yui"],"unavailable_models":["mimmi"]
            },partial.json()
            assert os.environ["RCLONE_CONFIG_ARCHIVE_COOKIE"]=="mimmi-cookie-fixture"
            assert os.environ["RCLONE_CONFIG_ARCHIVE_YUI_COOKIE"]=="yui-cookie-fixture"
            # Invalid Yui must not wipe a valid Mimmi session.
            partial=client.post(endpoint,headers=header,json={
                "cookie":"mimmi-cookie-fixture","yui_cookie":"invalid-yui"
            })
            assert partial.json()["models"]==["mimmi"],partial.text
            assert os.environ["RCLONE_CONFIG_ARCHIVE_YUI_COOKIE"]=="yui-cookie-fixture"
            assert client.post(endpoint,headers=header,json={
                "cookie":"incorrect-mimmi-session","yui_cookie":"invalid-yui"
            }).status_code==503
            assert client.post(endpoint,json={
                "cookie":"mimmi-cookie-fixture","yui_cookie":"yui-cookie-fixture"
            }).status_code==403
            assert client.post(endpoint,headers=header,json={
                "cookie":"short","yui_cookie":"yui-cookie-fixture"
            }).status_code==400
            print("GALLERY_SEPARATE_OIDC_OWNER_SESSIONS_AND_PARTIAL_RECOVERY_PASS")
finally:
    gateway.COOKIE=old_cookie
    gateway._cache.update(old_mimmi)
    gateway._yui_cache.update(old_yui)
