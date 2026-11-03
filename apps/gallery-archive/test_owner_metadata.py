"""Provider success-shaped JSON is never accepted as a verified owner document."""
import json
import os
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from read_owner_metadata import read,matches,ProviderVerificationRequired,read_with_current_owner_web_session,read_via_existing_owner_gateway
# Metadata integrity tests deliberately require no optional HTTP library.


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

    def test_known_provider_cat_challenge_allows_exact_same_account_file_download(self):
        # A normal file copy with current authorized credentials is distinct
        # from performing CAPTCHA/verification or trying a different account.
        def copied(command,**kwargs):
            self.assertEqual(command[:3],['rclone','copyto',self.remote])
            Path(command[3]).write_bytes(self.raw)
            return SimpleNamespace(returncode=0)
        with patch('read_owner_metadata.subprocess.run',side_effect=copied) as run:
            value=read(self.remote,'mimmi',reader=lambda *a,**k:b'{"errno":400141}')
        self.assertEqual(value,self.raw)
        self.assertEqual(run.call_count,1)

    def test_verification_required_when_both_same_account_read_methods_fail(self):
        with patch('read_owner_metadata.subprocess.run',return_value=SimpleNamespace(returncode=1)) as run:
            with self.assertRaises(ProviderVerificationRequired):
                read(self.remote,'mimmi',reader=lambda *a,**k:b'{"errno":400141}')
            self.assertEqual(run.call_count,1)
        def invalid(command,**kwargs):
            Path(command[3]).write_bytes(b'{"errno":400141}')
            return SimpleNamespace(returncode=0)
        with patch('read_owner_metadata.subprocess.run',side_effect=invalid):
            with self.assertRaises(ProviderVerificationRequired):
                read(self.remote,'mimmi',reader=lambda *a,**k:b'{"errno":400141}')


    def test_refreshes_existing_same_account_web_state_before_catalog_read(self):
        from unittest.mock import Mock
        token='t'*48
        def refresh():
            os.environ['RCLONE_CONFIG_ARCHIVE_JSTOKEN']=token
            return token
        def stored_reader(*args,**kwargs):
            self.assertEqual(os.environ.get('RCLONE_CONFIG_ARCHIVE_JSTOKEN'),token)
            return self.raw
        with patch.dict(os.environ,{},clear=False),patch('read_owner_metadata.subprocess.run') as file_copy:
            self.assertEqual(read_with_current_owner_web_session(
                self.remote,'mimmi',reader=stored_reader,refresh=refresh),self.raw)
            file_copy.assert_not_called()

    def test_existing_web_session_unavailable_preserves_cookie_only_sha_safe_read(self):
        def missing():
            raise ValueError('Owner session needs normal login')
        with patch('read_owner_metadata.subprocess.run') as file_copy:
            result=read_with_current_owner_web_session(
                self.remote,'mimmi',reader=lambda *a,**k:self.raw,refresh=missing)
            self.assertEqual(result,self.raw)
            file_copy.assert_not_called()

    def test_existing_session_refresh_never_bypasses_actual_provider_verification(self):
        with patch('read_owner_metadata.subprocess.run',return_value=SimpleNamespace(returncode=1)) as file_copy:
            with self.assertRaises(ProviderVerificationRequired):
                read_with_current_owner_web_session(
                    self.remote,'mimmi',reader=lambda *a,**k:b'{"errno":400141}',
                    refresh=lambda:'t'*48)
            self.assertEqual(file_copy.call_count,1)

    def test_wrong_archive_is_rejected_before_any_web_request(self):
        from unittest.mock import Mock
        refresh=Mock(return_value='t'*48)
        with self.assertRaises(ValueError):
            read_with_current_owner_web_session(
                'archive:Unknown/metadata/catalog.json','mimmi',
                reader=lambda *a,**k:self.raw,refresh=refresh)
        refresh.assert_not_called()


    def test_gateway_fallback_only_after_real_provider_verification_and_full_baseline(self):
        remote=self.remote
        invocations=[]
        def gateway_reader(uri,model,minimum):
            invocations.append((uri,model,minimum))
            return self.raw
        with patch('read_owner_metadata.subprocess.run',
                   return_value=SimpleNamespace(returncode=1)):
            result=read_with_current_owner_web_session(
                remote,'mimmi',minimum=1,
                reader=lambda *a,**k:b'{"errno":400141}',
                refresh=lambda:'t'*48,gateway_fallback=True,
                gateway_reader=gateway_reader)
        self.assertEqual(result,self.raw)
        self.assertEqual(invocations,[(remote,'mimmi',1)])

    def test_malformed_gateway_response_cannot_replace_private_owner_baseline(self):
        with patch('read_owner_metadata.subprocess.run',
                   return_value=SimpleNamespace(returncode=1)):
            with self.assertRaises(ProviderVerificationRequired):
                read_with_current_owner_web_session(
                    self.remote,'mimmi',minimum=1,
                    reader=lambda *a,**k:b'{"errno":400141}',
                    refresh=lambda:'t'*48,gateway_fallback=True,
                    gateway_reader=lambda *a,**k:b'{"errno":0,"albums":[]}')

    def test_signed_gateway_reader_only_uses_exact_render_and_actions_origins(self):
        import os
        from urllib.request import Request
        from urllib.parse import urlsplit
        class Reply:
            status=200
            def __init__(self,raw):self.raw=raw
            def __enter__(self):return self
            def __exit__(self,*args):return False
            def read(self,n):return self.raw[:n]
        seen=[]
        def opener(request,timeout):
            self.assertIsInstance(request,Request)
            seen.append((request.full_url,request.get_method(),timeout))
            if len(seen)==1:
                return Reply(json.dumps({'value':'x'*120}).encode())
            if len(seen)==2:
                return Reply(self.raw)
            raise AssertionError('Only two authenticated requests')
        with patch.dict(os.environ,{
            'ACTIONS_ID_TOKEN_REQUEST_URL':
                'https://pipelines.actions.githubusercontent.com/fixture?job=1',
            'ACTIONS_ID_TOKEN_REQUEST_TOKEN':'offline-actions-request-secret'
        }):
            result=read_via_existing_owner_gateway(
                self.remote,'mimmi',minimum=1,opener=opener)
        self.assertEqual(result,self.raw)
        self.assertEqual(len(seen),2)
        self.assertIn('audience=gallery-archive-terabox-sync',seen[0][0])
        self.assertEqual(seen[1][0],
            'https://mimmi-private-gallery-free.onrender.com/internal/gallery-owner-catalog/mimmi')
        self.assertEqual(seen[1][1],'POST')
        with patch.dict(os.environ,{
            'ACTIONS_ID_TOKEN_REQUEST_URL':'https://invalid.example/identity',
            'ACTIONS_ID_TOKEN_REQUEST_TOKEN':'offline-token'
        }):
            with self.assertRaises(ProviderVerificationRequired):
                read_via_existing_owner_gateway(self.remote,'mimmi',opener=opener)
        self.assertEqual(len(seen),2)


if __name__=='__main__':unittest.main(verbosity=2)
