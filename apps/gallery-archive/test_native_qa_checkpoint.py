"""A previous success is reusable only with actual native-job evidence and exact bytes."""
import copy
import json
import unittest

from native_qa_checkpoint import REPO,WORKFLOW,metadata_fingerprint,verify,resume_keys


class NativeCheckpointTests(unittest.TestCase):
    def setUp(self):
        def photo(n,sha):return {'number':n,'sha256':sha*64,'bytes':1000+n,'width':400,
            'height':600,'preview':True,'preview_sha256':str(n)*64}
        self.before={'model':'mimmi','albums':[{'id':'saved-work','images':[photo(1,'a')]}]}
        self.after={'model':'mimmi','albums':[{'id':'saved-work','images':[
            photo(1,'a'),photo(2,'b'),photo(3,'c')]}]}
        self.source='a'*40;self.baseline='b'*40
        self.document={'schema_version':1,'source_run_id':123,'source_owner_index_ref':self.source,
            'baseline_owner_index_ref':self.baseline,'source_indices_fingerprint':{
                'mimmi':metadata_fingerprint(self.after)},'jobs':[{'job_id':17,'model':'mimmi',
                    'browser':'webkit','shard':0,'shards':1}]}
        self.run={'head_sha':self.source,'head_branch':'main','head_repository':{'full_name':REPO},
            'path':WORKFLOW,'conclusion':'cancelled'}
        self.job={'id':17,'status':'completed','conclusion':'success',
            'name':'actual-deployed-originals (mimmi, 0, webkit, 1)'}
        self.report={'model':'mimmi','browser':'webkit','since_commit':self.baseline,
            'current_owner_index_ref':self.source,'shard':0,'shards':1,'success':True,
            'reload_pass':True,'TLS_verified_bridge':False,'page_errors':[],
            'all_new_or_upgraded_rows':2,'inventory':{'owner_rows':3},
            'photos':[{'album':'saved-work','number':n,'dimensions':[400,600],
                'thumbnail_decoded':True,'lightbox_decoded':True,'original_tab_decoded':True,
                'download_sha256_verified':True} for n in (2,3)]}

    def fetch(self,path,text=False):
        if path=='/actions/runs/123':return self.run
        if path=='/actions/runs/123/jobs?per_page=100':return {'total_count':1,'jobs':[self.job]}
        if path=='/actions/jobs/17/logs':
            return '2026-10-31T00:00:00Z DEPLOYED_PHYSICAL_PHOTOS_QA_PASS '+json.dumps(self.report)+'\n'
        if path=='raw:'+self.baseline+':mimmi':return self.before
        if path=='raw:'+self.source+':mimmi':return self.after
        raise AssertionError(path)

    def test_individually_completed_job_survives_an_unrelated_run_cancellation(self):
        self.assertEqual(verify(self.document,self.fetch),2)
        self.assertEqual(resume_keys(self.document,self.before,self.after,'mimmi','webkit',self.baseline),
            {('saved-work',2):17,('saved-work',3):17})
        self.assertEqual(resume_keys(self.document,self.before,self.after,'mimmi','chromium',self.baseline),{})

    def test_failed_cancelled_and_partial_jobs_never_count(self):
        for status in ['failure','cancelled',None]:
            self.job['conclusion']=status
            with self.assertRaises(ValueError):verify(self.document,self.fetch)
        self.job['conclusion']='success';self.report['photos'].pop()
        with self.assertRaises(ValueError):verify(self.document,self.fetch)

    def test_bridge_missing_download_sha_and_page_errors_are_not_native_success(self):
        original=copy.deepcopy(self.report)
        for update in [{'TLS_verified_bridge':True},{'page_errors':['real error']},{'reload_pass':False}]:
            self.report={**original,**update}
            with self.assertRaises(ValueError):verify(self.document,self.fetch)
        self.report=original;self.report['photos'][0]['download_sha256_verified']=False
        with self.assertRaises(ValueError):verify(self.document,self.fetch)

    def test_wrong_repo_commit_model_dimensions_and_duplicate_claims_fail_closed(self):
        self.run['head_repository']['full_name']='someone/other'
        with self.assertRaises(ValueError):verify(self.document,self.fetch)
        self.run['head_repository']['full_name']=REPO;self.run['head_sha']='d'*40
        with self.assertRaises(ValueError):verify(self.document,self.fetch)
        self.run['head_sha']=self.source;self.report['model']='yui'
        with self.assertRaises(ValueError):verify(self.document,self.fetch)
        self.report['model']='mimmi';self.report['photos'][0]['dimensions']=[200,300]
        with self.assertRaises(ValueError):verify(self.document,self.fetch)
        self.report['photos'][0]['dimensions']=[400,600]
        self.document['jobs'].append(copy.deepcopy(self.document['jobs'][0]))
        with self.assertRaises(ValueError):verify(self.document,self.fetch)

    def test_any_original_preview_or_inventory_change_requires_fresh_photo_checks(self):
        for field,value in [('sha256','d'*64),('preview_sha256','e'*64),('bytes',7777),('width',401)]:
            changed=copy.deepcopy(self.after);changed['albums'][0]['images'][1][field]=value
            self.assertEqual(resume_keys(self.document,self.before,changed,'mimmi','webkit',self.baseline),{})
        changed=copy.deepcopy(self.after);changed['albums'][0]['images'].append({
            **changed['albums'][0]['images'][1],'number':4})
        self.assertEqual(resume_keys(self.document,self.before,changed,'mimmi','webkit',self.baseline),{})
        self.assertEqual(resume_keys(self.document,self.before,self.after,'mimmi','webkit','c'*40),{})
        reordered=copy.deepcopy(self.after);reordered['albums'][0]['images'].reverse()
        self.assertEqual(resume_keys(self.document,self.before,reordered,'mimmi','webkit',self.baseline),{})

    def test_successful_nonoverlapping_jobs_from_two_runs_are_independently_verified(self):
        second_ref='c'*40
        first_job={**self.document['jobs'][0],'shards':2}
        second_job={**first_job,'job_id':18,'shard':1,'source_run_id':456,'source_owner_index_ref':second_ref}
        self.document['jobs']=[first_job,second_job]
        first_report={**self.report,'shards':2,'photos':[self.report['photos'][0]]}
        second_report={**self.report,'current_owner_index_ref':second_ref,'shards':2,'shard':1,
                       'photos':[self.report['photos'][1]]}
        def fetch(path,text=False):
            if path=='/actions/jobs/17/logs':return 'DEPLOYED_PHYSICAL_PHOTOS_QA_PASS '+json.dumps(first_report)
            if path=='/actions/runs/456':return {**self.run,'head_sha':second_ref}
            if path=='/actions/runs/456/jobs?per_page=100':return {'total_count':1,'jobs':[{**self.job,'id':18}]}
            if path=='/actions/jobs/18/logs':return 'DEPLOYED_PHYSICAL_PHOTOS_QA_PASS '+json.dumps(second_report)
            if path=='raw:'+second_ref+':mimmi':return self.after
            return self.fetch(path,text)
        self.assertEqual(verify(self.document,fetch),2)
        self.assertEqual(resume_keys(self.document,self.before,self.after,'mimmi','webkit',self.baseline),
                         {('saved-work',2):17,('saved-work',3):18})
        second_job['shard']=0;second_report.update({'shard':0,'photos':[self.report['photos'][0]]})
        with self.assertRaises(ValueError):verify(self.document,fetch)


if __name__=='__main__':unittest.main(verbosity=2)
