import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from transfer_individual_files import previously_verified_queues


class QueueResumeTests(unittest.TestCase):
    def test_local_queue_receipt_alone_never_skips_a_server_unverified_object(self):
        raw=json.dumps({'albums':[{'id':'saved-work','images':[{'sha256':'a'*64,'preview_sha256':'b'*64}]}]}).encode()
        pin=hashlib.sha256(raw).hexdigest()
        receipt={'album':'saved-work','pending_batch':hashlib.sha256((pin+'\nsaved-work').encode()).hexdigest(),
                 'remote_verified_photos':1}
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);path=root/'completed-work-queues.jsonl';path.write_text(json.dumps(receipt)+'\n')
            for acknowledged in [set(),{'a'*64}]:
                self.assertEqual(previously_verified_queues(root,raw,acknowledged),set())
            acknowledged={'a'*64,'b'*64}
            self.assertEqual(previously_verified_queues(root,raw,acknowledged),{'saved-work'})
            for changes in [{'pending_batch':'c'*64},{'remote_verified_photos':2},
                            {'remote_verified_photos':True},{'album':'other-work'}]:
                path.write_text(json.dumps({**receipt,**changes})+'\n')
                self.assertEqual(previously_verified_queues(root,raw,acknowledged),set())


if __name__=='__main__':unittest.main(verbosity=2)
