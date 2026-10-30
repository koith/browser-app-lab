#!/usr/bin/env python3
"""Polite HTTP retry regression tests; no external network requests."""
import unittest
from public_crawl_transport import build_session

class TestTransport(unittest.TestCase):
    def test_only_transient_status_retried(self):
        with build_session({"User-Agent":"ArchiveQualityCheck/1.0"}) as s:
            retry = s.get_adapter("https://").max_retries
            self.assertTrue(retry.is_retry("GET", 503))
            self.assertTrue(retry.is_retry("GET", 429, has_retry_after=True))
            self.assertFalse(retry.is_retry("GET", 403))
            self.assertFalse(retry.is_retry("GET", 451))
            self.assertFalse(retry.is_retry("POST", 503))
            self.assertTrue(retry.respect_retry_after_header)
            self.assertLessEqual(retry.total, 3)
            self.assertEqual(s.headers["User-Agent"],"ArchiveQualityCheck/1.0")

    def test_unbounded_network_retries_not_allowed(self):
        with self.assertRaises(ValueError):
            build_session({}, retries=100)

if __name__=="__main__":
    unittest.main(verbosity=2)
