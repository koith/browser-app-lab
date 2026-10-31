import unittest
import asyncio
import os
import tempfile
from pathlib import Path
from unittest.mock import patch
from gateway.cookie_format import cookie_header


class CookieFormatTests(unittest.TestCase):
    def test_raw_ndus_and_full_header_are_equivalent_without_value_changes(self):
        token='test-only-opaque-owner-value=='
        self.assertEqual(cookie_header(token),'ndus='+token)
        full='browserid=example; ndus='+token+'; lang=en'
        self.assertEqual(cookie_header(full),full)
        self.assertEqual(cookie_header('Cookie: '+full),full)
        self.assertEqual(cookie_header('  '+full+'  '),full)
        self.assertEqual(cookie_header(''),'')

    def test_header_injection_is_never_forwarded(self):
        for value in ['ndus=fixture\nX-Other: bad','ndus=fixture\r','ndus=fixture\x00',None]:
            with self.subTest(value=repr(value)):
                with self.assertRaises(ValueError):cookie_header(value)

    def test_existing_child_process_receives_header_without_mutating_parent(self):
        from gateway import main
        with tempfile.TemporaryDirectory() as folder:
            executable=Path(folder)/'rclone'
            executable.write_text('#!/usr/bin/env python3\nimport os,sys\n'
                'ok=os.environ.get("RCLONE_CONFIG_ARCHIVE_COOKIE")=="ndus=offline-fixture-only"\n'
                'sys.stdout.buffer.write(b"fixture-photo-bytes" if ok else b"incorrect-format")\n')
            executable.chmod(0o755)
            with patch.dict(os.environ,{'PATH':folder+os.pathsep+os.environ.get('PATH',''),
                                        'RCLONE_CONFIG_ARCHIVE_COOKIE':'offline-fixture-only'}):
                data=asyncio.run(main.rclone_bytes('originals/fixture/1.jpg',100))
                self.assertEqual(data,b'fixture-photo-bytes')
                self.assertEqual(os.environ['RCLONE_CONFIG_ARCHIVE_COOKIE'],'offline-fixture-only')


if __name__=='__main__':unittest.main(verbosity=2)
