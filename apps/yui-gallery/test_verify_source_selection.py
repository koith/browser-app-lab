"""Readback must match bytes and stop access/policy denials without retrying."""
import hashlib
import unittest
from unittest.mock import patch

import requests

from verify_source_selection import check


class ReadbackTests(unittest.TestCase):
    def test_unchanged_response_bytes_match(self):
        raw = b'unchanged source response'
        photo = {'album_id': 'work', 'number': 1, 'url': 'https://cdn.imgcup.com/photo.jpg',
                 'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest()}
        response = requests.Response();response.status_code = 200;response._content = raw
        client = unittest.mock.Mock();client.get.return_value = response
        self.assertTrue(check(photo, client)['source_readback_match'])
        client.get.assert_called_once_with(photo['url'])

    def test_denied_or_unverified_policy_stops_without_retry(self):
        photo = {'album_id': 'work', 'number': 1, 'url': 'https://cdn.imgcup.com/photo.jpg',
                 'bytes': 1, 'sha256': '0'*64}
        for status in (401,403,429,451):
            response = requests.Response();response.status_code = status
            client = unittest.mock.Mock();client.get.side_effect = requests.HTTPError('denied', response=response)
            with patch('verify_source_selection.time.sleep') as delay:
                self.assertFalse(check(photo, client)['source_readback_match'])
                delay.assert_not_called()
            client.get.assert_called_once()
        client = unittest.mock.Mock();client.get.side_effect = PermissionError('robots policy unverified')
        self.assertFalse(check(photo, client)['source_readback_match'])
        client.get.assert_called_once()


if __name__ == '__main__':
    unittest.main()
