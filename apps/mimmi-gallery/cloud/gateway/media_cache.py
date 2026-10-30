"""Bounded single-flight cache of owner media, only AFTER exact byte verification."""
import asyncio
import hashlib
from collections import OrderedDict


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
