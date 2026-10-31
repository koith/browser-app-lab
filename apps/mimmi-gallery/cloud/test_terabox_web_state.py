import asyncio
import unittest
from urllib.parse import quote

import httpx
from gateway.terabox_web_state import OwnerUploadState,WebStateUnavailable,extract_token,official_url


class WebStateTests(unittest.IsolatedAsyncioTestCase):
    async def test_normal_main_document_static_variants_and_cached_owner_binding(self):
        token='offline-upload-token-123456789'
        old='function fn(a){window.jsToken = a};fn("'+token+'")'
        self.assertEqual(extract_token('`'+quote(old,safe='')+'`'),token)
        self.assertEqual(extract_token('window.jsToken = "'+token+'";'),token)
        calls=[]
        def handle(request):
            calls.append(request)
            self.assertEqual(str(request.url),'https://www.terabox.com/main')
            self.assertIn(request.headers['cookie'],('ndus=offline-owner-session','ndus=offline-other-owner'))
            return httpx.Response(200,text='window.jsToken="'+token+'";')
        state=OwnerUploadState(httpx.MockTransport(handle))
        self.assertEqual(await state.get('ndus=offline-owner-session'),token)
        self.assertEqual(await state.get('ndus=offline-owner-session'),token)
        self.assertEqual(len(calls),1)
        await asyncio.gather(state.get('ndus=offline-other-owner'),state.get('ndus=offline-other-owner'))
        self.assertEqual(len(calls),2)

    async def test_denial_login_and_external_redirect_stop_without_credential_forwarding(self):
        for status,location in [(403,None),(451,None),(429,None),(302,'https://example.com/main'),
                                (302,'/login'),(302,'/challenge')]:
            calls=[]
            def handle(request):
                calls.append(request)
                return httpx.Response(status,headers={'location':location} if location else {},text='denied')
            with self.subTest(status=status,location=location):
                with self.assertRaises(WebStateUnavailable):
                    await OwnerUploadState(httpx.MockTransport(handle)).get('ndus=offline-owner-session')
                self.assertEqual(len(calls),1)
        for value in ['https://terabox.com.evil.test','http://www.terabox.com','https://user@www.terabox.com']:
            self.assertFalse(official_url(value))

    async def test_script_without_static_token_is_not_executed(self):
        with self.assertRaises(WebStateUnavailable):extract_token('window.jsToken = obtainSecretDynamically();')
        with self.assertRaises(WebStateUnavailable):extract_token('window.jsToken="short";')


if __name__=='__main__':unittest.main(verbosity=2)
