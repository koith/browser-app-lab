import json
from pathlib import Path
import unittest
from unittest.mock import patch,Mock
from check_independent_store_readiness import inspect

class ReadinessTests(unittest.TestCase):
 def test_missing_credentials_never_make_network_requests_or_claim_restoration(self):
  with patch('check_independent_store_readiness.check_existing_owner_budget',return_value={'objects':7724}):
   client=Mock();r=inspect(Path('.'),{},client)
  client.assert_not_called()
  self.assertFalse(r['gallery_restored']);self.assertFalse(r['zero_charge_account_verified'])
  self.assertEqual(r['uploaded_photos'],0);self.assertIn('GALLERY_MIRROR_ACCESS_KEY_ID',r['missing_secret_names'])
 def test_partially_configured_secret_values_are_never_in_report(self):
  e={'RCLONE_CONFIG_OWNERREPLICA_ACCESS_KEY_ID':'DO-NOT-PRINT-THIS-VALUE'}
  with patch('check_independent_store_readiness.check_existing_owner_budget',return_value={}):r=inspect(Path('.'),e)
  self.assertNotIn('DO-NOT-PRINT-THIS-VALUE',json.dumps(r))
 def test_sdk_exception_cannot_leak_private_bucket_or_keys(self):
  from check_independent_store_readiness import REQUIRED
  e={k:'private' for k in REQUIRED.values()}
  with patch('check_independent_store_readiness.check_existing_owner_budget',return_value={}),patch(
    'check_independent_store_readiness.validated_private_config',side_effect=ValueError('DO-NOT-PRINT-private-url')):
   r=inspect(Path('.'),e)
  self.assertNotIn('DO-NOT-PRINT',json.dumps(r));self.assertFalse(r['existing_private_bucket_readable'])

if __name__=='__main__':unittest.main(verbosity=2)
