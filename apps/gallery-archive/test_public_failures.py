"""Origin failures stop repeated work requests without loosening access rules."""
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

import requests

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'yui-gallery'))
from public_photo_archive import PublicSession,PublicOriginPaused,public_failure


def response(code,body=b'User-agent: *\nAllow: /\n'):
    r=requests.Response();r.status_code=code;r._content=body;r.url='https://fixture.example/work'
    return r


class PublicFailureTests(unittest.TestCase):
    def test_temporary_origin_pause_prevents_repeated_books_but_not_independent_sources(self):
        client=PublicSession(delay=0)
        with patch.object(client,'_raw',side_effect=[response(200),response(522),response(200),response(200),response(200)]) as read:
            with self.assertRaises(requests.HTTPError) as error:client.get('https://fixture.example/first')
            self.assertEqual(public_failure(error.exception)['cause'],'origin_temporarily_unavailable')
            with self.assertRaises(PublicOriginPaused):client.get('https://fixture.example/second')
            self.assertEqual(read.call_count,2)
            self.assertEqual(client.get('https://independent.example/work').status_code,200)
            self.assertEqual(read.call_count,4)
            client.cooldowns['https://fixture.example']=(0,522)
            self.assertEqual(client.get('https://fixture.example/first').status_code,200)

    def test_authentication_rate_and_legal_denials_stay_closed(self):
        for code in (401,403,429,451):
            with self.subTest(code=code):
                client=PublicSession(delay=0)
                with patch.object(client,'_raw',side_effect=[response(200),response(code)]) as read:
                    with self.assertRaises(requests.HTTPError):client.get('https://fixture.example/first')
                    with self.assertRaises(PublicOriginPaused) as error:client.get('https://fixture.example/second')
                    self.assertEqual(read.call_count,2)
                    self.assertEqual(public_failure(error.exception)['http_status'],code)

    def test_robots_failure_scope_and_redacted_error_classification(self):
        client=PublicSession(delay=0)
        with patch.object(client,'_raw',return_value=response(451)) as read:
            with self.assertRaises(PublicOriginPaused) as error:client.get('https://fixture.example/work')
            detail=public_failure(error.exception)
            self.assertEqual(detail['http_status'],451);self.assertEqual(detail['response_scope'],'robots_policy')
            self.assertEqual(read.call_count,1)
        error=requests.HTTPError('secret-cookie and signed-url must never become a report',response=response(404))
        detail=public_failure(error)
        self.assertEqual(detail['cause'],'public_resource_missing');self.assertNotIn('secret',str(detail))
        self.assertEqual(public_failure(requests.Timeout())['cause'],'transport_timeout')


if __name__=='__main__':unittest.main(verbosity=2)
