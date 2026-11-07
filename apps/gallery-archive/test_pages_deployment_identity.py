import json
import unittest
from pages_deployment_identity import identity,validate
from pages_single_publisher import publisher

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
 def test_native_build_must_name_the_exact_commit_without_fake_run_id(self):
  d={'schema_version':2,'repository':'koith/browser-app-lab','source_commit':'a'*40,'build_kind':'github-pages-jekyll'}
  self.assertEqual(validate(json.dumps(d),'a'*40),d)
  for edit in [{'source_commit':'b'*40},{'source_commit':'{{ site.github.build_revision }}'},
               {'repository':'other/repo'},{'build_kind':'unknown'},{'workflow_run_id':123}]:
   with self.subTest(edit=edit),self.assertRaises(ValueError):validate(json.dumps({**d,**edit}),'a'*40)
 def test_only_one_publisher_matches_the_existing_pages_mode(self):
  self.assertEqual(publisher({'build_type':'workflow'}),'workflow')
  self.assertEqual(publisher({'build_type':'legacy','source':{'branch':'main','path':'/'}}),'native')
  for config in [{'build_type':'unknown'},{'build_type':'legacy','source':{'branch':'other','path':'/'}},
                 {'build_type':'legacy','source':{'branch':'main','path':'/docs'}}]:
   with self.subTest(config=config),self.assertRaises(ValueError):publisher(config)

if __name__=='__main__':unittest.main(verbosity=2)
