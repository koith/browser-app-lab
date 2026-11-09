import json
import unittest
from unittest.mock import patch
from pages_deployment_identity import identity,validate
from pages_single_publisher import publisher,pages_gallery_equivalent

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

class GallerySupersededPagesTests(unittest.TestCase):
 def test_identical_source_is_valid_without_api(self):
  self.assertTrue(pages_gallery_equivalent('a'*40,'a'*40))
 def test_valid_descendant_identical_gallery_trees(self):
  with patch('pages_single_publisher._github_api',return_value={'status':'ahead','behind_by':0}) as api,patch(
       'pages_single_publisher._gallery_subtree_shas',
       side_effect=[{'mimmi-gallery':'filetree1','yui-gallery':'filetree2'},
                    {'mimmi-gallery':'filetree1','yui-gallery':'filetree2'}]) as trees:
   self.assertTrue(pages_gallery_equivalent('a'*40,'b'*40))
   api.assert_called_once_with('/compare/'+'a'*40+'...'+'b'*40+'?per_page=1')
   self.assertEqual(trees.call_count,2)
 def test_changed_gallery_must_never_pass(self):
  with patch('pages_single_publisher._github_api',return_value={'status':'ahead','behind_by':0}),patch(
       'pages_single_publisher._gallery_subtree_shas',
       side_effect=[{'mimmi-gallery':'A','yui-gallery':'B'},
                    {'mimmi-gallery':'A','yui-gallery':'CHANGED'}]):
   self.assertFalse(pages_gallery_equivalent('a'*40,'b'*40))
 def test_non_descendant_or_diverged_or_untrusted_ref_fails_closed(self):
  for result in [{'status':'behind','behind_by':1},{'status':'diverged','behind_by':1},
                 {'status':'ahead','behind_by':1}]:
   with self.subTest(result=result),patch('pages_single_publisher._github_api',return_value=result),patch(
        'pages_single_publisher._gallery_subtree_shas') as trees:
    self.assertFalse(pages_gallery_equivalent('a'*40,'b'*40))
    trees.assert_not_called()
  self.assertFalse(pages_gallery_equivalent('main','b'*40))
  self.assertFalse(pages_gallery_equivalent('a'*40,'https://not-a-commit'))

if __name__=='__main__':unittest.main(verbosity=2)
