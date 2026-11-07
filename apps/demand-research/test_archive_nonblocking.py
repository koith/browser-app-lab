"""Slow cloud reads must not freeze health/readiness or backup API admission."""
import asyncio
import threading
import time

import httpx
import gateway
import target_account_viewer as viewer
import target_archive_api
import backup_queue


def test_slow_account_library_does_not_block_health_or_backup_status(monkeypatch):
    monkeypatch.setattr(gateway,"TOKEN","synthetic-long-private-server-token-0123456789")
    monkeypatch.setattr(gateway,"COOKIE","synthetic-not-real-cloud-cookie")
    monkeypatch.setenv("DEMAND_PUBLIC_ARCHIVE_MODE","1")
    monkeypatch.setenv("DEMAND_ARCHIVE_QUEUE_MODE","1")
    monkeypatch.setattr(target_archive_api,"_last_request",None)
    queued=[]
    def accept(platform,account):
        queued.append((platform,account))
        return 1234567890
    monkeypatch.setattr(backup_queue,"create_request",accept)
    release=threading.Event()
    entered=threading.Event()

    class SlowCloud:
        def names(self,prefix):
            entered.set()
            # Bounded watchdog permits the pre-fix regression to fail, not hang.
            release.wait(timeout=1.2)
            return []

    monkeypatch.setattr(viewer,"open_root",SlowCloud)
    monkeypatch.setattr(viewer,"available_bundles",lambda _:[])

    async def exercise():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=gateway.app),base_url="https://testserver") as client:
            began=time.monotonic()
            library=asyncio.create_task(client.get("/api/account-archives"))
            try:
                await asyncio.sleep(0.04)
                health=await client.get("/health")
                status=await client.get("/api/target-archive/status")
                accepted=await client.post("/api/target-archive/start",
                    headers={"Origin":"https://testserver","X-Archive-Intent":"selected-public-account-v1"},
                    json={"platform":"bluesky","account":"bsky.app"})
                elapsed=time.monotonic()-began
                assert entered.is_set(),"slow actual archive route was not exercised"
                assert health.status_code==200 and status.status_code==200
                assert status.json()["enabled"] is True
                assert accepted.status_code==202
                assert accepted.json()["accepted"] is True
                assert queued==[("bluesky","bsky.app")]
                assert elapsed<0.65,"TeraBox library froze independent API requests"
            finally:
                release.set()
                result=await library
            assert result.status_code==200 and result.json()=={"accounts":[]}
    asyncio.run(exercise())
