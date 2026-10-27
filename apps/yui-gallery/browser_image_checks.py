"""Bounded retries for transient image transport failures in browser QA.

Never change a source URL, dimensions, checksum or expected image count.
Persistent failures still fail verification after two attempts.
"""
import asyncio
from playwright.async_api import Error


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
