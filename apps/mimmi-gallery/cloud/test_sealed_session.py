import asyncio
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from gateway.sealed_session import seal,restore


class ConnectionStateTests(unittest.TestCase):
    def test_only_same_existing_owner_key_can_restore_without_plaintext_export(self):
        cookie='ndus=offline-owner-test-cookie';key='offline-existing-server-token'
        state=seal(cookie,key)
        self.assertNotIn(cookie,state);self.assertEqual(restore(state,key),cookie)
        for value,secret in [(state,'different-owner-token'),(state[:-3]+'abc',key),('not-sealed',key)]:
            with self.assertRaises(ValueError):restore(value,secret)

    def test_fresh_process_restores_before_first_storage_read(self):
        key='offline-existing-server-token';cookie='ndus=offline-restored-cookie'
        with tempfile.TemporaryDirectory() as folder:
            executable=Path(folder)/'rclone'
            executable.write_text('#!/usr/bin/env python3\nimport os,sys\n'
                'good=os.environ.get("RCLONE_CONFIG_ARCHIVE_COOKIE")=="ndus=offline-restored-cookie"\n'
                'sys.stdout.buffer.write(b"verified-photo" if good else b"wrong-startup-state")\n')
            executable.chmod(0o755)
            env={**os.environ,'PATH':folder+os.pathsep+os.environ.get('PATH',''),
                 'GALLERY_ACCESS_TOKEN':key,'RCLONE_CONFIG_ARCHIVE_COOKIE':'expired-fixture',
                 'ARCHIVE_STORAGE_STATE_SEALED':seal(cookie,key)}
            code='import asyncio;from gateway import main;assert asyncio.run(main.rclone_bytes("originals/fixture/1.jpg",100))==b"verified-photo"'
            result=subprocess.run([sys.executable,'-c',code],cwd=Path(__file__).parent,env=env,
                                  capture_output=True,text=True,timeout=20)
            self.assertEqual(result.returncode,0,result.stderr[-500:])
            self.assertNotIn(cookie,result.stdout+result.stderr)
            self.assertIn('OWNER_STORAGE_CONNECTION_RESTORED',result.stdout)


if __name__=='__main__':unittest.main(verbosity=2)
