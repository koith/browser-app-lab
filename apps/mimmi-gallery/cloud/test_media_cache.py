import asyncio
import hashlib
import unittest
from gateway.media_cache import VerifiedMediaCache


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


if __name__=='__main__':unittest.main(verbosity=2)
