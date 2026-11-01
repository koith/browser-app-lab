import os
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch
from owner_upload_web_token import (
    obtain_cookie_and_token,update_current_process,write_github_env,
    WebStateUnavailable
)


class DummyWebState:
    async def get(self,cookie,origin):
        if cookie!='ndus=example-owner-cookie' or origin!='https://www.terabox.com':
            raise AssertionError('Unexpected account or origin')
        return 'w'*48


class WebStateTests(unittest.TestCase):
    def test_reuse_exact_gateway_client_token_for_rclone_upload(self):
        cookie,token=obtain_cookie_and_token(
            'example-owner-cookie',DummyWebState())
        self.assertEqual(cookie,'ndus=example-owner-cookie')
        self.assertEqual(token,'w'*48)
        with patch.dict(os.environ,{},clear=False):
            self.assertEqual(update_current_process(
                'example-owner-cookie',DummyWebState()),'w'*48)
            self.assertEqual(os.environ['RCLONE_CONFIG_ARCHIVE_JSTOKEN'],'w'*48)
            self.assertEqual(os.environ['RCLONE_CONFIG_ARCHIVE_COOKIE'],
                             'ndus=example-owner-cookie')

    def test_github_environment_is_written_only_to_private_env_path(self):
        with TemporaryDirectory() as d:
            dest=Path(d)/'env'
            dest.write_text('existing=yes\n')
            write_github_env(dest,'example-owner-cookie',DummyWebState())
            rows=dest.read_text().splitlines()
            self.assertIn('RCLONE_CONFIG_ARCHIVE_JSTOKEN='+'w'*48,rows)
            self.assertIn('existing=yes',rows)
            self.assertEqual(len(rows),2)

    def test_reject_missing_or_invalid_public_upload_session(self):
        class NoToken:
            async def get(self,cookie,origin):
                raise WebStateUnavailable('Owner normal login required')
        with self.assertRaises(WebStateUnavailable):
            obtain_cookie_and_token('example-owner-cookie',NoToken())
        class BadToken:
            async def get(self,cookie,origin):return 'bad\nvalue'
        with self.assertRaises(WebStateUnavailable):
            obtain_cookie_and_token('example-owner-cookie',BadToken())


if __name__=='__main__':
    unittest.main(verbosity=2)
