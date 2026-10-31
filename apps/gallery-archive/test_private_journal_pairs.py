"""Partial storage failures retain exact healthy pairs without source/auth bypass."""
import copy
import hashlib
from io import BytesIO
import json
import unittest
from unittest.mock import patch

from PIL import Image
import test_deferred_verified_batch as fixtures
from private_collection_snapshot import STATE
from recover_private_journal_pairs import recover,producer_proof,CREATORS


class JournalPairsTests(unittest.TestCase):
    setUp=fixtures.DeferredBatchTests.setUp
    write=fixtures.DeferredBatchTests.write

    def source(self):
        good={k:v for k,v in self.photo.items() if k not in ('source_photo_number','work_identity_saved_cut_anchors')}
        good['number']=11
        bad={**good,'number':12,'key':'originals/saved-work/12-new.jpg',
             'sha256':'d'*64,'bytes':len(self.original_bytes)}
        self.owner['albums'][0]['title']='Saved work'
        source={'schema_version':1,'model':'mimmi','state':STATE,'remote_media_verified':False,
            'pending_admission_queue':False,'catalog':{'schema_version':1,'model':'mimmi','albums':[
                {'id':'saved-work','images':[good,bad]}]},'collection_audit':{'model':'mimmi','results':[
                    {'id':'saved-work','engine':'requests_scoped_public_pagination'}]}}
        reviewed={'saved-work':{'source':CREATORS['mimmi']}}
        preview=(self.stage/self.photo['preview']).read_bytes();calls=[]
        def reader(args,limit):
            calls.append(args[1])
            if args[1].endswith('/12-new.jpg'):return b'{"errno":400141,"errmsg":"need verify"}'
            return preview if '/previews/' in args[1] else self.original_bytes
        return source,reviewed,reader,calls

    def test_one_denied_original_keeps_only_the_other_complete_pair_and_exact_bytes(self):
        source,reviewed,reader,calls=self.source();before=copy.deepcopy(self.owner)
        target=self.stage/'recovery'
        result=recover(source,self.owner,reviewed,target,reader)
        self.assertEqual(result,{'photos':1,'held':1,'skipped':0})
        self.assertEqual(len(calls),3,'Denied original must never be retried or followed by its preview')
        self.assertEqual(self.owner,before)
        catalog=json.loads((target/'metadata/catalog.json').read_text());row=catalog['albums'][0]['images'][0]
        self.assertEqual((target/row['key']).read_bytes(),self.original_bytes)
        self.assertEqual(row['number'],11)
        report=json.loads((target/'metadata/remote-verification.json').read_text())
        self.assertEqual((report['media_checked'],report['failed']),(2,0))
        self.assertIn('only_selected_complete',report['scope'])
        audit=json.loads((target/'metadata/collection-audit.json').read_text())
        self.assertEqual(audit['held_photos'][0]['cause'],'provider_errno_400141')
        self.assertIsNone(audit['held_photos'][0]['source_file_number'],'Archive slots are not public source numbers')

    def test_bad_preview_is_not_a_valid_pair_and_existing_originals_are_never_replaced(self):
        source,reviewed,reader,calls=self.source();source['catalog']['albums'][0]['images']=source['catalog']['albums'][0]['images'][:1]
        def bad_preview(args,limit):
            return b'{"errno":400141}' if '/previews/' in args[1] else self.original_bytes
        result=recover(source,self.owner,reviewed,self.stage/'no-pair',bad_preview)
        self.assertEqual((result['photos'],result['held']),(0,1))
        row=source['catalog']['albums'][0]['images'][0];row['higher_resolution_replacement']=True
        with patch('recover_private_journal_pairs.storage') as external:
            result=recover(source,self.owner,reviewed,self.stage/'replacement',external)
            self.assertEqual((result['photos'],result['held']),(0,1));external.assert_not_called()

    def test_wrong_creator_changed_work_context_and_unsafe_key_cannot_trigger_a_read(self):
        source,reviewed,reader,calls=self.source()
        with patch('recover_private_journal_pairs.storage') as external:
            with self.assertRaises(ValueError):recover(source,self.owner,{'saved-work':{'source':CREATORS['yui']}},self.stage/'wrong',external)
            external.assert_not_called()
        source['catalog']['albums'][0]['images'][0]['key']='originals/saved-work/../../outside.jpg'
        with patch('recover_private_journal_pairs.storage') as external:
            with self.assertRaises(ValueError):recover(source,self.owner,reviewed,self.stage/'unsafe',external)
            external.assert_not_called()

    def test_visual_work_retains_exact_failed_public_source_number(self):
        source,reviewed,reader,calls=self.source();reviewed['saved-work'].update(visual_reference_required=True,source='https://sexy.pixibb.com/mimmi-work/')
        self.owner['albums'][0]['images']=[{'number':n,'sha256':str(n)*64} for n in (1,2,3)]
        context=source['collection_audit']['results'][0];context.update(source=reviewed['saved-work']['source'],
            saved_reference_anchors=3,unresolved_source_numbers=[],saved_cut_correspondence=[{
                'owner_archive_number':n,'owner_sha256':str(n)*64,'whole_frame_visual_error':0} for n in (1,2,3)])
        for number,row in enumerate(source['catalog']['albums'][0]['images'],4):
            row.update(source_photo_number=number,work_identity_saved_cut_anchors=3,
                source_numbering='public_web_filename_not_publisher_original')
        target=self.stage/'visual';result=recover(source,self.owner,reviewed,target,reader)
        self.assertEqual((result['photos'],result['held']),(1,1))
        audit=json.loads((target/'metadata/collection-audit.json').read_text())
        self.assertEqual(audit['results'][0]['unresolved_source_numbers'],[5])
        self.assertFalse(audit['results'][0]['source_edition_all_files_accounted_for'])

    def test_a_digest_from_the_wrong_producer_log_cannot_authorize_private_journal_read(self):
        request={'model':'mimmi','producer_run':123,'producer_attempt':1,'producer_head':'a'*40,
            'expected_collected_photos':2,'journal_sha256':'b'*64}
        run={'head_sha':'a'*40,'head_branch':'main','head_repository':{'full_name':'koith/browser-app-lab'},
             'path':'.github/workflows/gallery-direct-individual-archive.yml'}
        jobs={'total_count':1,'jobs':[{'id':1,'name':'collect-store-readback (mimmi)','steps':[{
            'name':'Preserve unverified source correspondence privately before any original transfer','conclusion':'success'}]}]}
        response=type('Response',(),{'content':b'not matching','text':'not matching','raise_for_status':lambda self:None})()
        with patch.dict('os.environ',{'GH_TOKEN':'unit-test-only'}),patch('recover_private_journal_pairs.github',side_effect=[run,jobs]),patch('recover_private_journal_pairs.requests.get',return_value=response):
            with self.assertRaisesRegex(ValueError,'producer log digest'):producer_proof(request)

    def test_a_changed_inventory_fails_before_reading_any_private_journal_or_image(self):
        import sys
        from recover_private_journal_pairs import main
        owner=copy.deepcopy(self.owner);owner['storage']='owner-private-terabox-sha-verified-bytes'
        owner['albums'][0]['images']=[{**self.photo,'number':10,'sha256':'a'*64}]
        owner_path=self.stage/'owner.json';owner_path.write_text(json.dumps(owner))
        request={'schema_version':1,'scope':'existing_private_photos_only','models':{'mimmi':{
            'model':'mimmi','producer_run':123,'producer_attempt':1,'producer_head':'a'*40,
            'expected_collected_photos':2,'journal_sha256':'b'*64,'baseline_owner_fingerprint':'0'*64}}}
        request_path=self.stage/'request.json';request_path.write_text(json.dumps(request))
        args=['recovery','--request',str(request_path),'--model','mimmi','--owner',str(owner_path),
              '--stage',str(self.stage/'guarded'),'--github-output',str(self.stage/'out')]
        with patch.object(sys,'argv',args),patch('recover_private_journal_pairs.producer_proof'),patch('recover_private_journal_pairs.storage') as external:
            with self.assertRaisesRegex(ValueError,'QA-completed publication baseline'):main()
            external.assert_not_called()


if __name__=='__main__':unittest.main(verbosity=2)
