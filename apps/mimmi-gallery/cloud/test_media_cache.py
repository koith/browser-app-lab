import asyncio
import hashlib
import unittest
from fastapi import HTTPException
from gateway.media_cache import VerifiedMediaCache,read_media_with_transport_recovery


class CacheTests(unittest.IsolatedAsyncioTestCase):
    async def test_simultaneous_requests_share_verified_read(self):
        cache=VerifiedMediaCache();calls=[];raw=b'original bytes'
        async def load():
            calls.append(1);await asyncio.sleep(.02);return raw
        sha=hashlib.sha256(raw).hexdigest()
        values=await asyncio.gather(*(cache.get('mimmi','originals/a.jpg',len(raw),sha,load) for _ in range(12)))
        self.assertEqual(values,[raw]*12);self.assertEqual(len(calls),1)
        self.assertEqual(await cache.get('mimmi','originals/a.jpg',len(raw),sha,load),raw)
        self.assertEqual(len(calls),1)

    async def test_corrupt_bytes_are_never_cached(self):
        cache=VerifiedMediaCache();raw=b'original'
        async def wrong():return b'corrupted'
        sha=hashlib.sha256(raw).hexdigest()
        with self.assertRaises(ValueError):await cache.get('yui','originals/a.jpg',len(raw),sha,wrong)
        await asyncio.sleep(0)
        self.assertFalse(cache.values);self.assertFalse(cache.pending)
        async def right():return raw
        self.assertEqual(await cache.get('yui','originals/a.jpg',len(raw),sha,right),raw)

    async def test_namespace_digest_and_bounded_lru(self):
        cache=VerifiedMediaCache(max_bytes=6,max_entry=4);calls=[]
        async def get(model,data):
            async def load():calls.append(model);return data
            return await cache.get(model,'originals/a.jpg',len(data),hashlib.sha256(data).hexdigest(),load)
        await get('yui',b'1111');await get('mimmi',b'1111')
        self.assertEqual(calls,['yui','mimmi']);self.assertEqual(cache.bytes,4)
        await get('mimmi',b'2222');self.assertEqual(cache.bytes,4)
        await get('mimmi',b'12345');self.assertEqual(cache.bytes,4)

    async def test_remote_concurrency_is_bounded(self):
        cache=VerifiedMediaCache(workers=2);active=0;peak=0;raw=b'valid'
        async def load():
            nonlocal active,peak
            active+=1;peak=max(peak,active);await asyncio.sleep(.02);active-=1;return raw
        await asyncio.gather(*(cache.get('mimmi',str(i),len(raw),hashlib.sha256(raw).hexdigest(),load) for i in range(8)))
        self.assertEqual(peak,2)

    async def test_cancelled_waiter_does_not_cancel_other_browser(self):
        cache=VerifiedMediaCache();raw=b'photo';gate=asyncio.Event();calls=[]
        async def load():calls.append(1);await gate.wait();return raw
        args=('yui','originals/a.jpg',len(raw),hashlib.sha256(raw).hexdigest(),load)
        first=asyncio.create_task(cache.get(*args));await asyncio.sleep(0)
        second=asyncio.create_task(cache.get(*args));first.cancel();gate.set()
        self.assertEqual(await second,raw);self.assertEqual(len(calls),1)


class TransportRecoveryTests(unittest.IsolatedAsyncioTestCase):
    async def test_one_classified_read_recovers_then_exact_SHA_is_still_required(self):
        raw=b'exact original bytes';calls=[]
        async def reader():
            calls.append(1)
            if len(calls)==1:raise HTTPException(502,'Cloud media unavailable',
                headers={'X-Archive-Read-Cause':'transport_interruption'})
            return raw
        cache=VerifiedMediaCache()
        async def load():return await read_media_with_transport_recovery(reader)
        result=await cache.get('mimmi','originals/a.jpg',len(raw),hashlib.sha256(raw).hexdigest(),load)
        self.assertEqual(result,raw);self.assertEqual(len(calls),2)

    async def test_denial_verification_integrity_and_unclassified_errors_are_not_retried(self):
        for error in [HTTPException(401),HTTPException(403),HTTPException(429),HTTPException(451),
                      HTTPException(503,'Storage verification required'),HTTPException(502,'integrity mismatch'),
                      HTTPException(502,'unclassified remote read failed')]:
            calls=[]
            async def reader():calls.append(1);raise error
            with self.subTest(status=error.status_code):
                with self.assertRaises(HTTPException):await read_media_with_transport_recovery(reader)
                self.assertEqual(len(calls),1)

    async def test_second_failure_or_wrong_bytes_cannot_establish_cached_success(self):
        calls=[]
        async def interrupted():
            calls.append(1);raise HTTPException(502,'interrupted',
                headers={'X-Archive-Read-Cause':'transport_interruption'})
        with self.assertRaises(HTTPException):await read_media_with_transport_recovery(interrupted)
        self.assertEqual(len(calls),2)
        calls.clear()
        async def wrong():
            calls.append(1)
            if len(calls)==1:raise HTTPException(502,'interrupted',
                headers={'X-Archive-Read-Cause':'transport_interruption'})
            return b'corrupt'
        cache=VerifiedMediaCache()
        async def load():return await read_media_with_transport_recovery(wrong)
        with self.assertRaises(ValueError):
            await cache.get('yui','originals/a.jpg',7,hashlib.sha256(b'correct').hexdigest(),load)
        self.assertFalse(cache.values);self.assertEqual(len(calls),2)

    async def test_the_original_total_deadline_cancels_a_slow_read_without_extra_time(self):
        stopped=[]
        async def slow():
            try:await asyncio.sleep(10)
            finally:stopped.append(True)
        with self.assertRaises(HTTPException) as error:
            await read_media_with_transport_recovery(slow,deadline_seconds=.03)
        self.assertEqual(error.exception.status_code,504);self.assertEqual(stopped,[True])


if __name__=='__main__':unittest.main(verbosity=2)
