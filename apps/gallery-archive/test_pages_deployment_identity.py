import json
import unittest
from pages_deployment_identity import identity,validate

class DeploymentIdentityTests(unittest.TestCase):
 def test_exact_deployment_source_is_accepted(self):
  d=identity('a'*40,123);self.assertEqual(validate(json.dumps(d),'a'*40),d)
 def test_latest_main_is_not_a_substitute_for_the_operating_commit(self):
  with self.assertRaises(ValueError):validate(json.dumps(identity('b'*40,123)),'a'*40)
 def test_missing_malformed_or_untrusted_stamps_cannot_pass(self):
  original=identity('a'*40,123)
  for edit in [{'repository':'other/repo'},{'source_commit':'main'},{'workflow_run_id':0},
               {'schema_version':0},{'workflow_run_id':True}]:
   with self.subTest(edit=edit),self.assertRaises(ValueError):validate(json.dumps({**original,**edit}),'a'*40)
  with self.assertRaises(ValueError):validate('{}','a'*40)

if __name__=='__main__':unittest.main(verbosity=2)
