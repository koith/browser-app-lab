"""Offline capacity gate for verified account ZIPs (no SNS credentials)."""
from __future__ import annotations
import threading

from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
import target_account_viewer as viewer


def app_client():
    app=FastAPI()
    app.include_router(viewer.create_router(lambda request: None))
    return TestClient(app)


def test_all_heavy_reader_routes_refuse_overload_without_touching_archive(monkeypatch):
    class Saturated:
        attempts=0
        def acquire(self,timeout):
            assert timeout == viewer._ARCHIVE_READ_WAIT_SECONDS
            self.attempts+=1
            return False
        def release(self):
            raise AssertionError("never release unacquired capacity")
    gate=Saturated()
    monkeypatch.setattr(viewer,"_ARCHIVE_READ_SLOT",gate)
    monkeypatch.setattr(viewer,"open_account",lambda *args: (
        (_ for _ in ()).throw(AssertionError("must not decrypt on overload"))
    ))
    key="bluesky-"+"a"*40
    paths=[
        f"/api/account-archives/{key}/backup-status",
        f"/api/account-archives/{key}/profile",
        f"/api/account-archives/{key}/feed",
        f"/api/account-archives/{key}/graph/followers",
        f"/api/account-archives/{key}/threads/{'a'*40}",
        f"/api/account-archives/{key}/media/{'a'*40}/0",
        f"/api/account-archives/{key}/profile-asset/avatar",
    ]
    with app_client() as client:
        for path in paths:
            response=client.get(path)
            assert response.status_code==503, (path,response.text[:100])
            assert response.headers.get("retry-after")=="3",path
            assert "no-store" in response.headers.get("cache-control",""),path
    assert gate.attempts==len(paths)


def test_capacity_lease_always_released_after_read_failure(monkeypatch):
    class Lease:
        entered=0
        released=0
        def acquire(self,timeout):
            self.entered+=1
            return True
        def release(self):
            self.released+=1
    gate=Lease()
    monkeypatch.setattr(viewer,"_ARCHIVE_READ_SLOT",gate)
    def missing(_):
        raise HTTPException(404,"Synthetic source not found")
    monkeypatch.setattr(viewer,"open_account",missing)
    with app_client() as client:
        response=client.get("/api/account-archives/bluesky-"+("c"*40)+"/profile")
        assert response.status_code==404
    assert gate.entered==gate.released==1


def test_production_capacity_is_one_verified_archive_read_at_a_time():
    # The free service has 512 MiB memory. Serializing only load_account is
    # insufficient if prior requests still hold decoded ZIPs as response data.
    assert isinstance(viewer._ARCHIVE_READ_SLOT,type(threading.BoundedSemaphore()))
    assert viewer._ARCHIVE_READ_SLOT._value==1
