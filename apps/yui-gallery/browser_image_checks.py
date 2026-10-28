"""Bounded retries for transient image transport failures in browser QA.

Never change a source URL, dimensions, checksum or expected image count.
Persistent failures still fail verification after two attempts.
"""
import asyncio
from playwright.async_api import Error
from urllib.parse import urlsplit


async def decode_image(image, timeout_ms=25000):
    for attempt in range(2):
        try:
            await image.evaluate('''(im, timeout)=>Promise.race([
              im.decode(),new Promise((_,reject)=>setTimeout(()=>reject(Error('Image decode timed out: '+im.src)),timeout))
            ])''', timeout_ms)
            return attempt
        except Error as error:
            transient = any(text in str(error).lower() for text in [
                'image decode timed out', 'source image cannot be decoded',
                'image could not be decoded', 'encodingerror: loading error'])
            if attempt or not transient:
                raise
            print('IMAGE_DECODE_RETRY_SAME_URL', flush=True)
            await asyncio.sleep(.5)
            await image.evaluate('''im=>{
              const src=im.getAttribute('src');if(!src)throw Error('Missing image src');
              im.removeAttribute('src');im.setAttribute('src',src)
            }''')


class SourceViewPacer:
    """Space viewer actions for a rate-sensitive public CDN; keep direct requests."""
    def __init__(self, interval=1.0, hosts=('cdn.imgcup.com',)):
        self.interval = interval
        self.hosts = set(hosts)
        self.lock = asyncio.Lock()
        self.next_view = 0.0
        self.views = 0

    async def wait(self, url):
        if urlsplit(url).hostname not in self.hosts:
            return
        async with self.lock:
            loop = asyncio.get_running_loop()
            delay = self.next_view - loop.time()
            if delay > 0:
                await asyncio.sleep(delay)
            self.next_view = loop.time() + self.interval
            self.views += 1
