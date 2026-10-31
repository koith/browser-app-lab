import hashlib
import sys
import time
import unittest
from pathlib import Path
import tempfile
from verify_terabox import read_remote,read_remote_with_recovery,RemoteCommandFailure


class RemoteDeadlineTests(unittest.TestCase):
    def test_partial_transport_read_recovers_once_inside_original_deadline(self):
        with tempfile.TemporaryDirectory() as tmp:
            state=Path(tmp)/'attempt'
            script=('from pathlib import Path;import sys;'
                    'p=Path(sys.argv[1]);n=int(p.read_text())+1 if p.exists() else 1;p.write_text(str(n));'
                    'sys.stdout.write("a" if n==1 else "abc");'
                    'sys.stderr.write("ERROR: unexpected EOF https://example.invalid/?token=secret");'
                    'sys.exit(1 if n==1 else 0)')
            start=time.monotonic()
            self.assertEqual(read_remote_with_recovery(('fixture',3,hashlib.sha256(b'abc').hexdigest()),'unused',3,
                [sys.executable,'-c',script,str(state)]),'fixture')
            self.assertEqual(state.read_text(),'2');self.assertLess(time.monotonic()-start,3)

    def test_denial_and_successful_wrong_bytes_never_retry_or_leak_urls(self):
        for data,code,message in [('','1','HTTP 403 unexpected EOF'),('abd','0','ERROR: unexpected EOF')]:
            with self.subTest(code=code),tempfile.TemporaryDirectory() as tmp:
                state=Path(tmp)/'attempt'
                script=('from pathlib import Path;import sys;'
                        'p=Path(sys.argv[1]);p.write_text(p.read_text()+"x" if p.exists() else "x");'
                        'sys.stdout.write(sys.argv[2]);sys.stderr.write(sys.argv[4]);sys.exit(int(sys.argv[3]))')
                with self.assertRaises(ValueError) as failed:
                    read_remote_with_recovery(('fixture',3,hashlib.sha256(b'abc').hexdigest()),'unused',3,
                        [sys.executable,'-c',script,str(state),data,code,message+' https://example.invalid/?token=secret'])
                self.assertEqual(state.read_text(),'x');self.assertNotIn('example.invalid',str(failed.exception))
                self.assertNotIn('token=secret',str(failed.exception))
                if code=='1':self.assertFalse(failed.exception.retryable_transport)

    def test_stalled_stream_is_killed_before_eof(self):
        start=time.monotonic()
        with self.assertRaises(TimeoutError):
            read_remote(('fixture',3,hashlib.sha256(b'abc').hexdigest()),'unused',.2,
                [sys.executable,'-c','import time,sys;sys.stdout.buffer.write(b"a");sys.stdout.flush();time.sleep(30)'])
        self.assertLess(time.monotonic()-start,2)

    def test_provider_verification_body_is_rejected_without_retry_or_payload_leak(self):
        with tempfile.TemporaryDirectory() as tmp:
            state=Path(tmp)/'attempt'
            script=('from pathlib import Path;import sys;'
                    'p=Path(sys.argv[1]);p.write_text(p.read_text()+"x" if p.exists() else "x");'
                    'print(\'{"errno":400141,"errmsg":"private-response-not-for-logs"}\')')
            with self.assertRaises(ValueError) as failed:
                read_remote_with_recovery(('fixture',1000,'a'*64),'unused',3,
                    [sys.executable,'-c',script,str(state)])
            self.assertEqual(state.read_text(),'x')
            self.assertIn('errno=400141',str(failed.exception));self.assertIn('verification_required=True',str(failed.exception))
            self.assertNotIn('private-response',str(failed.exception))

    def test_exact_byte_readback_and_corruption(self):
        row=('fixture',3,hashlib.sha256(b'abc').hexdigest())
        self.assertEqual(read_remote(row,'unused',2,[sys.executable,'-c','print("abc",end="")']),'fixture')
        with self.assertRaises(ValueError):
            read_remote(row,'unused',2,[sys.executable,'-c','print("abd",end="")'])


if __name__=='__main__':unittest.main(verbosity=2)
