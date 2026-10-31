"""Bounded single-flight cache of owner media, only AFTER exact byte verification."""
import asyncio
import hashlib
from collections import OrderedDict
from fastapi import HTTPException


async def read_media_with_transport_recovery(reader, *, deadline_seconds=115):
    """One retry for an explicitly classified interrupted read, same total cap.

    Never retry authorization, verification, legal denials or integrity errors.
    The caller still checks every returned byte against the original SHA.
    """
    if not 0<deadline_seconds<=115:raise ValueError('Invalid existing media read deadline')
    async def bounded_read():
        try:return await reader()
        except HTTPException as error:
            if (error.status_code!=502 or
                    (error.headers or {}).get('X-Archive-Read-Cause')!='transport_interruption'):
                raise
            print('OWNER_MEDIA_CLASSIFIED_TRANSPORT_READ_RECOVERY',flush=True)
            await asyncio.sleep(.2)
            return await reader()
    try:return await asyncio.wait_for(bounded_read(),timeout=deadline_seconds)
    except asyncio.TimeoutError:
        raise HTTPException(status_code=504,detail='Cloud read timed out') from None


class VerifiedMediaCache:
    def __init__(self, max_bytes=48*1024*1024, max_entry=12*1024*1024, workers=2):
        self.max_bytes, self.max_entry = max_bytes, max_entry
        self.values = OrderedDict()
        self.pending = {}
        self.bytes = 0
        self.workers = asyncio.Semaphore(workers)

    def clear(self):
        self.values.clear()
        self.bytes = 0

    async def get(self, namespace, path, size, sha, loader):
        key = (namespace, path, size, sha)
        if key in self.values:
            self.values.move_to_end(key)
            return self.values[key]
        task = self.pending.get(key)
        if task is None:
            async def load():
                async with self.workers:
                    data = await loader()
                    if len(data) != size or hashlib.sha256(data).hexdigest() != sha:
                        raise ValueError('Remote image integrity mismatch')
                    if len(data) <= self.max_entry:
                        self.values[key] = data
                        self.bytes += len(data)
                        while self.bytes > self.max_bytes:
                            _, previous = self.values.popitem(last=False)
                            self.bytes -= len(previous)
                    return data
            task = asyncio.create_task(load())
            self.pending[key] = task
            def complete(future):
                if self.pending.get(key) is future:
                    self.pending.pop(key, None)
                # Retrieve errors even when every waiting browser disconnected.
                if not future.cancelled():
                    future.exception()
            task.add_done_callback(complete)
        # Scrolling away must not cancel the shared read for other viewers.
        return await asyncio.shield(task)
