"""Provider success-shaped JSON is never accepted as a verified owner document."""
import json
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from read_owner_metadata import read,matches


class OwnerMetadataTests(unittest.TestCase):
    def setUp(self):
        p={'number':1,'sha256':'a'*64,'bytes':2000,'width':400,'height':600,
            'key':'originals/saved-work/photo.jpg','preview':'previews/saved-work/photo.webp',
            'preview_sha256':'b'*64,'preview_bytes':1000}
        self.document={'schema_version':1,'model':'mimmi','storage':'owner-private-terabox-sha-verified-bytes',
            'albums':[{'id':'saved-work','images':[p]}]}
        self.raw=json.dumps(self.document).encode();self.remote='archive:MimmiArchive/metadata/catalog.json'

    def test_valid_original_stream_is_returned_unchanged_without_another_request(self):
        with patch('read_owner_metadata.subprocess.run') as run:
            self.assertEqual(read(self.remote,'mimmi',reader=lambda *a,**k:self.raw),self.raw)
            run.assert_not_called()

    def test_successful_provider_error_uses_one_normal_same_account_file_download(self):
        def copied(command,**kwargs):Path(command[3]).write_bytes(self.raw);return SimpleNamespace(returncode=0)
        with patch('read_owner_metadata.subprocess.run',side_effect=copied) as run:
            raw=read(self.remote,'mimmi',reader=lambda *a,**k:b'{"errno":31066,"errmsg":"untrusted-private-value"}')
        self.assertEqual(raw,self.raw)
        self.assertEqual(run.call_count,1)
        self.assertEqual(run.call_args.args[0][:3],['rclone','copyto',self.remote])

    def test_wrong_model_partial_catalog_and_bad_queue_are_never_admitted(self):
        self.assertFalse(matches(self.raw,'yui',None,1))
        self.assertFalse(matches(self.raw,'mimmi',None,2))
        doc={**self.document,'source_batch_sha256':'c'*64};raw=json.dumps(doc).encode()
        self.assertFalse(matches(raw,'mimmi','d'*64,1))
        def still_bad(command,**kwargs):Path(command[3]).write_bytes(b'{"errno":-9}');return SimpleNamespace(returncode=0)
        with patch('read_owner_metadata.subprocess.run',side_effect=still_bad):
            with self.assertRaises(ValueError) as error:read(self.remote,'mimmi',reader=lambda *a,**k:b'{"errno":-9}')
        self.assertIn('provider_errno',str(error.exception))
        self.assertNotIn('untrusted-private-value',str(error.exception))

    def test_failed_auth_command_does_not_switch_account_or_attempt_another_method(self):
        def denied(*a,**k):raise ValueError('existing authenticated command denied')
        with patch('read_owner_metadata.subprocess.run') as run:
            with self.assertRaises(ValueError):read(self.remote,'mimmi',reader=denied)
            run.assert_not_called()
        with self.assertRaises(ValueError):read('archive:OtherOwner/metadata/catalog.json','mimmi',reader=denied)


if __name__=='__main__':unittest.main(verbosity=2)
