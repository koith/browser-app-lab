import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from commit_verified_owner_catalog import commit


class VerifiedCatalogCommitTests(unittest.TestCase):
    def test_exact_verified_catalog_commits_after_delayed_provider_visibility(self):
        with TemporaryDirectory() as d:
            stage=Path(d)/'stage';(stage/'metadata').mkdir(parents=True)
            cat={'model':'yui','schema_version':1,
                 'storage':'owner-private-terabox-sha-verified-bytes',
                 'albums':[{'id':'work','images':[]}]}
            proof={'model':'yui','media_checked':2,'full_SHA256_verified':2,
                   'photos':1,'failed':0,'verified_specs_sha256':'a'*64}
            raw=(json.dumps(cat)+'\n').encode()
            (stage/'metadata/catalog.json').write_bytes(raw)
            (stage/'metadata/remote-verification.json').write_text(json.dumps(proof))
            called=[]
            def uploader(args):
                called.append(args)
                return 4
            def reader(location,target,expected):
                self.assertEqual(expected,raw)
                self.assertEqual(target,'archive:YuiArchive/metadata/catalog.json')
                return 'remote_file_readback'
            out=Path(d)/'verified.json'
            report=commit(stage,'yui','archive:YuiArchive',out,
                          uploader=uploader,reader=reader)
            self.assertEqual(report['write_command_exit'],4)
            self.assertEqual(out.read_bytes(),raw)
            self.assertEqual(called[0][0],'copyto')

    def test_no_remote_sha_proof_means_no_catalog_write(self):
        with TemporaryDirectory() as d:
            stage=Path(d)/'stage';(stage/'metadata').mkdir(parents=True)
            (stage/'metadata/catalog.json').write_text(json.dumps({
                'model':'mimmi','schema_version':1,
                'storage':'owner-private-terabox-sha-verified-bytes',
                'albums':[]}))
            (stage/'metadata/remote-verification.json').write_text(json.dumps({
                'model':'mimmi','media_checked':2,'full_SHA256_verified':1,
                'failed':1,'photos':1}))
            calls=[]
            with self.assertRaisesRegex(ValueError,'Refuse unverified'):
                commit(stage,'mimmi','archive:MimmiArchive',Path(d)/'out',
                       uploader=lambda a:calls.append(a))
            self.assertEqual(calls,[])
            self.assertFalse((Path(d)/'out').exists())

    def test_owner_catalog_must_not_replace_verified_metadata_with_wrong_bytes(self):
        with TemporaryDirectory() as d:
            stage=Path(d)/'stage';(stage/'metadata').mkdir(parents=True)
            (stage/'metadata/catalog.json').write_text(json.dumps({
                'model':'mimmi','schema_version':1,
                'storage':'owner-private-terabox-sha-verified-bytes',
                'albums':[]}))
            (stage/'metadata/remote-verification.json').write_text(json.dumps({
                'model':'mimmi','media_checked':2,'full_SHA256_verified':2,
                'failed':0,'photos':1,'verified_specs_sha256':'a'*64}))
            def reader(stage,target,expected):
                raise ValueError('Exact catalog remote SHA differs')
            with self.assertRaisesRegex(ValueError,'Exact catalog remote'):
                commit(stage,'mimmi','archive:MimmiArchive',Path(d)/'out',
                       uploader=lambda args:0,reader=reader)
            self.assertFalse((Path(d)/'out').exists())


if __name__=='__main__':
    unittest.main(verbosity=2)
