"""Validate complete-byte recovery through the same authenticated storage client."""
import hashlib
import sys
import unittest
from verify_terabox import read_remote_with_recovery

class OwnerCopytoTests(unittest.TestCase):
    def test_full_sha_recovery_and_corruption_rejection(self):
        cat_script='print(\'{"errno":400141}\')'
        copy_script='from pathlib import Path;import sys;Path(sys.argv[1]).write_bytes(sys.argv[2].encode())'
        original='a'*120
        row=('original.jpg',len(original),hashlib.sha256(original.encode()).hexdigest())
        self.assertEqual(read_remote_with_recovery(
            row,'local',3,[sys.executable,'-c',cat_script],
            [sys.executable,'-c',copy_script,'{dest}',original]),'original.jpg')
        with self.assertRaisesRegex(ValueError,'SHA256 integrity mismatch'):
            read_remote_with_recovery(
                row,'local',3,[sys.executable,'-c',cat_script],
                [sys.executable,'-c',copy_script,'{dest}','b'*120])
        with self.assertRaisesRegex(ValueError,'wrong byte length'):
            read_remote_with_recovery(
                row,'local',3,[sys.executable,'-c',cat_script],
                [sys.executable,'-c',copy_script,'{dest}','shorter'])

if __name__=='__main__':unittest.main(verbosity=2)
