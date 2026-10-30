import hashlib
import sys
import time
import unittest
from verify_terabox import read_remote


class RemoteDeadlineTests(unittest.TestCase):
    def test_stalled_stream_is_killed_before_eof(self):
        start=time.monotonic()
        with self.assertRaises(TimeoutError):
            read_remote(('fixture',3,hashlib.sha256(b'abc').hexdigest()),'unused',.2,
                [sys.executable,'-c','import time,sys;sys.stdout.buffer.write(b"a");sys.stdout.flush();time.sleep(30)'])
        self.assertLess(time.monotonic()-start,2)

    def test_exact_byte_readback_and_corruption(self):
        row=('fixture',3,hashlib.sha256(b'abc').hexdigest())
        self.assertEqual(read_remote(row,'unused',2,[sys.executable,'-c','print("abc",end="")']),'fixture')
        with self.assertRaises(ValueError):
            read_remote(row,'unused',2,[sys.executable,'-c','print("abd",end="")'])


if __name__=='__main__':unittest.main(verbosity=2)
