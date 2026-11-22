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
from recover_private_journal_pairs import recover,producer_proof,prior_recovery_proof,completed_baseline_proof,CREATORS
from merge_incremental import checked_row,merge
from publish_owner_index import clean_catalog


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

    def test_storage_census_ignores_source_and_never_reads_media_or_publishes(self):
        from recover_private_journal_pairs import census_journal_storage
        source,reviewed,reader,calls=self.source()
        photo=source['catalog']['albums'][0]['images'][0]
        def list_only(args,limit):
            calls.append(args)
            self.assertEqual(args[0],'lsjson')
            field,size=('key','bytes') if '/originals/' in args[1] else ('preview','preview_bytes')
            return json.dumps([{'Name':photo[field].rsplit('/',1)[1],'Size':photo[size]}]).encode()
        report=census_journal_storage(source,self.owner,self.stage/'census',list_only)
        self.assertEqual(len(calls),2)
        self.assertEqual(report['not_indexed'],2)
        self.assertEqual(report['counts']['pairs_size_match'],1)
        self.assertEqual(report['counts']['pairs_incomplete'],1)
        self.assertFalse(report['sha_verified'])
        self.assertFalse(report['gallery_published'])

    def test_private_recovery_indexes_only_verified_existing_originals(self):
        from recover_private_journal_pairs import verify_existing_private_inventory
        source,reviewed,reader,calls=self.source()
        photo=source['catalog']['albums'][0]['images'][0]
        def existing(args,limit):
            if args[0]=='lsjson':
                field,size=('key','bytes') if '/originals/' in args[1] else ('preview','preview_bytes')
                return json.dumps([{'Name':photo[field].rsplit('/',1)[1],'Size':photo[size]}]).encode()
            return reader(args,limit)
        target=self.stage/'private-recovered'
        result=verify_existing_private_inventory(source,self.owner,target,existing)
        self.assertEqual(result['verified_originals'],1)
        self.assertEqual(result['counts']['preview_verified'],1)
        self.assertEqual(result['counts']['original_unavailable'],1)
        self.assertEqual(result['albums'][0]['images'][0]['key'],photo['key'])
        self.assertFalse(result['public_gallery_published'])
        self.assertEqual(result['new_media_uploaded'],0)
        self.assertEqual(result,json.loads((target/'metadata/private-recovered-index.json').read_text()))

    def test_storage_census_reports_failed_listing_as_unknown(self):
        from recover_private_journal_pairs import census_journal_storage
        source,reviewed,reader,calls=self.source()
        result=census_journal_storage(source,self.owner,self.stage/'unknown',lambda args,limit:None)
        self.assertEqual(result['counts']['pairs_unknown'],2)

    def test_exact_publisher_manifest_recovery_never_reads_unknown_photo(self):
        source,reviewed,reader,calls=self.source()
        row=source['catalog']['albums'][0]['images'][0]
        proof={'saved-work':{(row['sha256'],row['bytes'],row['width'],row['height'])}}
        result=recover(source,self.owner,reviewed,self.stage/'official-exact',reader,
                       publisher_samples=proof)
        self.assertEqual((result['photos'],result['held'],len(calls)),(1,1,2))
        audit=json.loads((self.stage/'official-exact/metadata/collection-audit.json').read_text())
        self.assertEqual(audit['held_photos'][0]['cause'],'no_exact_publisher_manifest_photo')

    def test_new_producer_log_readback_method_format_is_accepted(self):
        request={'model':'mimmi','producer_run':123,'producer_attempt':1,'producer_head':'a'*40,
                 'expected_collected_photos':500,'journal_sha256':'b'*64}
        run={'head_sha':'a'*40,'head_branch':'main','head_repository':{'full_name':'koith/browser-app-lab'},
             'path':'.github/workflows/gallery-direct-individual-archive.yml'}
        jobs={'total_count':1,'jobs':[{'id':1,'name':'collect-store-readback (mimmi)','steps':[{
            'name':'Preserve unverified source correspondence privately before any original transfer','conclusion':'success'}]}]}
        line='PRIVATE_UNVERIFIED_SOURCE_JOURNAL_PRESERVED mimmi 500 READBACK_METHOD remote_cat METADATA_SHA '+'b'*64
        response=type('Response',(),{'content':line.encode(),'text':line,'raise_for_status':lambda self:None})()
        with patch.dict('os.environ',{'GH_TOKEN':'unit-test-only'}),patch('recover_private_journal_pairs.github',side_effect=[run,jobs]),patch('recover_private_journal_pairs.requests.get',return_value=response):
            producer_proof(request)

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

    def test_400141_preview_can_be_recovered_by_full_sha_copyto(self):
        source,reviewed,reader,calls=self.source()
        source['catalog']['albums'][0]['images']=source['catalog']['albums'][0]['images'][:1]
        preview=(self.stage/self.photo['preview']).read_bytes()
        def provider(args,limit):
            return b'{"errno":400141}' if '/previews/' in args[1] else self.original_bytes
        attempts=[]
        def alternate(path,limit):
            attempts.append(path)
            return preview
        accepted=recover(source,self.owner,reviewed,self.stage/'copyto-accepted',provider,copyto=alternate)
        self.assertEqual((accepted['photos'],accepted['held']),(1,0))
        self.assertEqual(len(attempts),1)
        self.assertIn('/previews/',attempts[0])
        corrupted=recover(source,self.owner,reviewed,self.stage/'copyto-wrong-sha',provider,
                          copyto=lambda path,limit:preview[:-1]+b'x')
        self.assertEqual((corrupted['photos'],corrupted['held']),(0,1))
        report=json.loads((self.stage/'copyto-wrong-sha/metadata/collection-audit.json').read_text())
        self.assertEqual(report['held_photos'][0]['cause'],'copyto_exact_SHA_or_byte_length_mismatch')
        attempts.clear()
        denied=recover(source,self.owner,reviewed,self.stage/'other-provider-error',
                       lambda args,limit:b'{"errno":31045}' if '/previews/' in args[1] else self.original_bytes,
                       copyto=lambda path,limit:attempts.append(path))
        self.assertEqual((denied['photos'],denied['held'],attempts),(0,1,[]))

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

    def test_live_baseline_accepts_appends_but_rejects_lost_or_changed_slots(self):
        from recover_private_journal_pairs import require_live_published_inventory
        owner=copy.deepcopy(self.owner)
        owner['storage']='owner-private-terabox-sha-verified-bytes'
        owner['albums'][0]['images']=[{**self.photo,'number':10,'sha256':'a'*64}]
        published=clean_catalog(owner,'mimmi')
        grown=copy.deepcopy(owner)
        grown['albums'][0]['images'].append({**self.photo,'number':11,'sha256':'b'*64})
        require_live_published_inventory(grown,'mimmi',published)
        with self.assertRaisesRegex(ValueError,'lose or change'):
            require_live_published_inventory(grown,'mimmi',clean_catalog(
                {**owner,'albums':[{**owner['albums'][0],'images':[
                    {**self.photo,'number':10,'sha256':'c'*64}]}]},'mimmi'))
        with self.assertRaisesRegex(ValueError,'lose or change'):
            require_live_published_inventory(owner,'mimmi',clean_catalog(grown,'mimmi'))

    def test_already_recovered_sha_is_skipped_and_new_slots_follow_live_inventory(self):
        source,reviewed,reader,calls=self.source()
        row=source['catalog']['albums'][0]['images'][0]
        self.owner['albums'][0]['images'].append({**row,'number':99})
        result=recover(source,self.owner,reviewed,self.stage/'already-recovered',reader)
        self.assertEqual((result['photos'],result['held'],result['skipped']),(0,1,1))
        self.assertEqual(len(calls),1)
        self.owner['albums'][0]['images'][-1]['sha256']='c'*64
        result=recover(source,self.owner,reviewed,self.stage/'append-after-99',reader)
        saved=json.loads((self.stage/'append-after-99'/'metadata/catalog.json').read_text())
        self.assertEqual(saved['albums'][0]['images'][0]['number'],100)

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

    def test_preview_only_hold_reads_exact_original_once_never_denied_preview_or_original(self):
        source,reviewed,reader,calls=self.source()
        audit={'model':'mimmi','held_photos':[
            {'work':'saved-work','archive_collection_number':11,'role':'preview'},
            {'work':'saved-work','archive_collection_number':12,'role':'original'}]}
        target=self.stage/'original-only'
        result=recover(source,self.owner,reviewed,target,reader,preview_hold_audit=audit)
        self.assertEqual(result,{'photos':1,'held':0,'skipped':0})
        self.assertEqual(len(calls),1);self.assertIn('/originals/',calls[0])
        doc=json.loads((target/'metadata/catalog.json').read_text());row=doc['albums'][0]['images'][0]
        self.assertEqual((target/row['key']).read_bytes(),self.original_bytes)
        self.assertEqual(row['preview_fallback'],'verified-original')
        self.assertTrue(all(k not in row for k in ('preview','preview_bytes','preview_sha256')))
        doc['storage']='owner-private-terabox-sha-verified-bytes'
        self.assertNotIn('preview',clean_catalog(doc,'mimmi')['albums'][0]['images'][0])
        proof=json.loads((target/'metadata/remote-verification.json').read_text())
        self.assertEqual((proof['photos'],proof['media_checked'],proof['full_SHA256_verified']),(1,1,1))

    def test_original_corruption_is_still_held_and_is_not_retried(self):
        source,reviewed,reader,calls=self.source();calls=[]
        def corrupted(args,limit):calls.append(args);return self.original_bytes[:-1]+b'!'
        audit={'model':'mimmi','held_photos':[{'work':'saved-work','archive_collection_number':11,'role':'preview'}]}
        target=self.stage/'corruption';result=recover(source,self.owner,reviewed,target,corrupted,preview_hold_audit=audit)
        self.assertEqual((result['photos'],result['held'],len(calls)),(0,1,1))
        self.assertEqual(json.loads((target/'metadata/collection-audit.json').read_text())['held_photos'][0]['role'],'original')

    def test_original_thumbnail_schema_cannot_mask_missing_previews_or_affect_yui(self):
        row={k:v for k,v in self.photo.items() if not k.startswith('preview')}
        with self.assertRaises(ValueError):checked_row('mimmi','saved-work',row)
        row['preview_fallback']='verified-original';checked_row('mimmi','saved-work',row)
        with self.assertRaises(ValueError):checked_row('yui','saved-work',row)
        for field,value in [('preview',self.photo['preview']),('preview_sha256','a'*64),('preview_bytes',500)]:
            with self.subTest(field=field),self.assertRaises(ValueError):
                checked_row('mimmi','saved-work',{**row,field:value})

    def test_original_only_baseline_survives_merge_and_only_staged_readback_counts_photos(self):
        import verify_terabox
        source,reviewed,reader,calls=self.source()
        audit={'model':'mimmi','held_photos':[{'work':'saved-work','archive_collection_number':11,'role':'preview'}]}
        target=self.stage/'roundtrip';recover(source,self.owner,reviewed,target,reader,preview_hold_audit=audit)
        old=copy.deepcopy(self.owner);old['albums'][0]['images']=[{**self.photo,'number':10,'sha256':'a'*64,
            'key':'originals/saved-work/old.jpg','preview':'previews/saved-work/old.webp'}]
        previous=self.stage/'previous.json';previous.write_text(json.dumps(old))
        merge(target,previous,'mimmi')
        with patch.object(verify_terabox,'read_remote_with_recovery',side_effect=lambda row,remote:row[0]) as remote:
            proof=verify_terabox.verify(target,'archive:MimmiArchive',1,only_staged=True)
        self.assertEqual((proof['photos'],proof['media_checked'],remote.call_count),(1,1,1))
        previous.write_bytes((target/'metadata/catalog.json').read_bytes())
        # An unchanged original-only row has no separate preview to delete.
        report=merge(target,previous,'mimmi');self.assertEqual(report['unchanged'],2)

    def test_unpreserved_prior_audit_cannot_select_any_private_photo(self):
        run={'head_sha':'a'*40,'head_branch':'main','head_repository':{'full_name':'koith/browser-app-lab'},
             'path':'.github/workflows/gallery-existing-private-journal-recovery.yml'}
        jobs={'total_count':1,'jobs':[{'name':'recover-already-stored-pairs (mimmi)','steps':[]}]}
        with patch('recover_private_journal_pairs.github',side_effect=[run,jobs]):
            with self.assertRaisesRegex(ValueError,'independently preserved'):
                prior_recovery_proof({'run':123,'attempt':1,'head':'a'*40},'mimmi')

    def test_partial_or_wrong_native_baseline_never_authorizes_the_next_publication(self):
        document={'completed_baseline_native_QA_run':123,'completed_owner_index_commit':'a'*40}
        run={'head_sha':'a'*40,'head_branch':'main','head_repository':{'full_name':'koith/browser-app-lab'},
             'path':'.github/workflows/gallery-newly-stored-photo-qa.yml','status':'completed','conclusion':'success'}
        with patch('recover_private_journal_pairs.github',return_value=run):completed_baseline_proof(document)
        for change in [{'conclusion':'failure'},{'status':'in_progress'},{'head_sha':'b'*40},{'head_branch':'other'},
                       {'path':'.github/workflows/static.yml'}]:
            with self.subTest(change=change),patch('recover_private_journal_pairs.github',return_value={**run,**change}):
                with self.assertRaisesRegex(ValueError,'has not completed'):completed_baseline_proof(document)


class ExactArticleContinuationTests(unittest.TestCase):
    setUp=fixtures.DeferredBatchTests.setUp
    write=fixtures.DeferredBatchTests.write
    source=JournalPairsTests.source

    def setup_transaction(self,preview=True):
        import recover_private_journal_pairs as recovery
        source,reviewed,reader,calls=self.source()
        source['collection_audit']['results'][0].update(engine=recovery.ARTICLE_ENGINE,
            individual_files_saved=2,new_staged_files_from_alternative_engines=2)
        photo=source['catalog']['albums'][0]['images'][0]
        row={k:photo[k] for k in ('number','key','sha256','bytes','width','height')}
        if preview:row.update({k:photo[k] for k in ('preview','preview_bytes','preview_sha256')})
        else:row['preview_status']='unverified_or_missing'
        counts={'already_indexed':0,'original_unavailable':1,'original_verified':1,'preview_verified':int(preview)}
        self.enterContext(patch.dict(recovery.ARTICLE_COUNTS,counts,clear=True))
        self.enterContext(patch.dict(recovery.ARTICLE_WORK_COUNTS,{'saved-work':2},clear=True))
        inventory={'schema_version':1,'model':'mimmi','scope':'private_existing_object_inventory_not_publication',
            'source_journal_rows':2,'verified_originals':1,'counts':counts,
            'new_media_uploaded':0,'public_gallery_published':False,
            'albums':[{'id':'saved-work','images':[row]}]}
        audit={'model':'mimmi','private_verified_counts':counts,'media_read':True,'gallery_published':False,
            'details':[{'work':'saved-work','archive_collection_number':11,'original_status':'size_match'},
                       {'work':'saved-work','archive_collection_number':12,'original_status':'missing'}]}
        return source,inventory,audit,copy.deepcopy(self.owner),reviewed,reader,calls

    def run_recovery(self,parts,**kwargs):
        from recover_private_journal_pairs import recover_trusted_article
        source,inventory,audit,producer_owner,reviewed,reader,calls=parts
        return recover_trusted_article(source,inventory,audit,self.owner,producer_owner,reviewed,
            kwargs.get('exclusions',{}),self.stage/kwargs.get('name','continued'),kwargs.get('reader',reader))

    def test_only_exact_reviewed_producer_command_work_counts_and_recovery_can_continue(self):
        from recover_private_journal_pairs import ARTICLE_PRODUCER,ARTICLE_RECOVERY,ARTICLE_WORK_COUNTS,trusted_article_producer
        request={**ARTICLE_PRODUCER,'trusted_article_recovery':ARTICLE_RECOVERY}
        command='python apps/gallery-archive/direct_photo_pipeline.py --model "$MODEL" --owner "$RUNNER_TEMP/owner-before.json" --max-new 500 --max-pages 60 --alternative-engines --reviewed-source-only'
        log=command+'\n'+'\n'.join('DIRECT_WORK_SOURCE_EVIDENCE mimmi '+aid+' '+json.dumps({
            'individual_files_saved':count,'new_staged_files_from_alternative_engines':count}) for aid,count in ARTICLE_WORK_COUNTS.items())
        proof={'job':{'id':136439087942,'steps':[{
            'name':'Collect all observed public pages into individually verified files, without photo ZIPs','conclusion':'success'}]},'log':log}
        trusted_article_producer(request,proof)
        for field,value in [('producer_run',44779438810),('producer_attempt',2),('producer_head','a'*40),
                            ('journal_sha256','a'*64),('trusted_article_recovery',{**ARTICLE_RECOVERY,'attempt':2}),
                            ('storage_census_only',True),('official_publisher_sha_only',True)]:
            with self.subTest(field=field),self.assertRaises(ValueError):trusted_article_producer({**request,field:value},proof)
        for changed in [log.replace('--reviewed-source-only',''),log.replace('--max-new 500','--max-new 501'),
                        log.replace('"individual_files_saved": 120','"individual_files_saved": 119')]:
            with self.subTest(log=changed[:100]),self.assertRaises(ValueError):trusted_article_producer(request,{**proof,'log':changed})

    def test_exact_intersection_fresh_readback_and_append_preserve_original_keys(self):
        parts=self.setup_transaction();before=copy.deepcopy(self.owner)
        result=self.run_recovery(parts)
        self.assertEqual(result,{'photos':1,'held':1,'skipped':0})
        self.assertEqual(self.owner,before)
        photo=parts[0]['catalog']['albums'][0]['images'][0]
        saved=json.loads((self.stage/'continued/metadata/catalog.json').read_text())['albums'][0]['images'][0]
        self.assertEqual((saved['key'],saved['sha256']),(photo['key'],photo['sha256']))
        self.assertEqual((self.stage/'continued'/saved['key']).read_bytes(),self.original_bytes)
        self.assertEqual(len(parts[-1]),2)
        audit=json.loads((self.stage/'continued/metadata/collection-audit.json').read_text())
        self.assertEqual((audit['new_local_individual_files'],audit['new_unique_cuts_claimed'],audit['gallery_open_verified_files']),(0,0,0))
        self.assertEqual(audit['held_photos'][0]['archive_collection_number'],12)

    def test_changed_signature_or_recovery_inventory_rejected_before_remote_request(self):
        parts=self.setup_transaction()
        for field,value in [('sha256','b'*64),('bytes',999),('width',700),('key','originals/saved-work/other.jpg'),
                            ('preview_sha256','e'*64)]:
            changed=copy.deepcopy(parts[:5])+parts[5:]
            changed[1]['albums'][0]['images'][0][field]=value
            with self.subTest(field=field),self.assertRaises(ValueError):self.run_recovery(changed)
        self.assertEqual(parts[-1],[])
        parts[2]['details'][0]['original_status']='missing'
        with self.assertRaises(ValueError):self.run_recovery(parts)
        self.assertEqual(parts[-1],[])

    def test_unregistered_producer_or_current_work_and_wrong_engine_are_rejected(self):
        parts=self.setup_transaction()
        old=copy.deepcopy(parts[3]);parts[3]['albums']=[]
        with self.assertRaisesRegex(ValueError,'registered existing'):self.run_recovery(parts)
        parts[3].update(old);self.owner['albums']=[]
        with self.assertRaisesRegex(ValueError,'registered existing'):self.run_recovery(parts)
        self.owner=copy.deepcopy(old)
        parts[0]['collection_audit']['results'][0]['engine']='arbitrary_article'
        with self.assertRaisesRegex(ValueError,'engine or work counts'):self.run_recovery(parts)
        self.assertEqual(parts[-1],[])

    def test_missing_or_corrupted_bytes_stay_held_without_fallback_or_source_retry(self):
        parts=self.setup_transaction()
        for name,raw in [('missing',None),('changed',self.original_bytes[:-1]+b'!')]:
            calls=[]
            def reader(args,limit):calls.append(args);return raw
            result=self.run_recovery(parts,reader=reader,name=name)
            self.assertEqual(result,{'photos':0,'held':2,'skipped':0})
            self.assertEqual(len(calls),1)

    def test_owner_duplicate_sha_is_skipped_without_remote_read_even_at_another_slot(self):
        parts=self.setup_transaction();photo=parts[0]['catalog']['albums'][0]['images'][0]
        self.owner['albums'][0]['images'].append({**photo,'number':99})
        self.assertEqual(self.run_recovery(parts),{'photos':0,'held':1,'skipped':1})
        self.assertEqual(parts[-1],[])

    def test_new_slot_follows_latest_owner_and_merge_keeps_old_bytes_metadata(self):
        parts=self.setup_transaction()
        old={**self.photo,'number':99,'key':'originals/saved-work/old.jpg',
             'preview':'previews/saved-work/old.webp','sha256':'a'*64}
        self.owner['albums'][0]['images']=[old]
        before=self.stage/'live-before.json';before.write_text(json.dumps(self.owner))
        self.run_recovery(parts)
        merged=merge(self.stage/'continued',before,'mimmi')
        rows=json.loads((self.stage/'continued/metadata/catalog.json').read_text())['albums'][0]['images']
        self.assertEqual(merged['new_photos'],1)
        self.assertEqual(rows[0],old)
        self.assertEqual(rows[1]['number'],100)
        self.assertEqual(rows[1]['key'],self.photo['key'])

    def test_matching_sha_does_not_override_wrong_decoded_dimensions(self):
        parts=self.setup_transaction()
        parts[0]['catalog']['albums'][0]['images'][0]['width']=401
        parts[1]['albums'][0]['images'][0]['width']=401
        result=self.run_recovery(parts)
        self.assertEqual(result['photos'],0)
        held=json.loads((self.stage/'continued/metadata/collection-audit.json').read_text())['held_photos']
        self.assertEqual(held[0]['cause'],'original_decoded_dimensions_or_format_changed')

    def test_only_prior_missing_preview_uses_exact_original_without_requesting_preview(self):
        parts=self.setup_transaction(preview=False)
        self.assertEqual(self.run_recovery(parts)['photos'],1)
        self.assertEqual(len(parts[-1]),1)
        row=json.loads((self.stage/'continued/metadata/catalog.json').read_text())['albums'][0]['images'][0]
        self.assertEqual(row['preview_fallback'],'verified-original')
        self.assertTrue(all(k not in row for k in ('preview','preview_bytes','preview_sha256')))
        checked_row('mimmi','saved-work',row)
        self.assertEqual((self.stage/'continued'/row['key']).read_bytes(),self.original_bytes)

    def test_new_preview_failure_does_not_expand_prior_one_original_fallback(self):
        parts=self.setup_transaction()
        result=self.run_recovery(parts,reader=lambda args,limit:None if '/previews/' in args[1] else self.original_bytes)
        self.assertEqual(result['photos'],0)
        held=json.loads((self.stage/'continued/metadata/collection-audit.json').read_text())['held_photos']
        self.assertEqual(held[0]['role'],'preview')

    def test_current_identity_exclusion_preserved_without_reading_selected_object(self):
        parts=self.setup_transaction()
        result=self.run_recovery(parts,exclusions={'excluded_album_ids':['saved-work']})
        self.assertEqual(result,{'photos':0,'held':2,'skipped':0});self.assertEqual(parts[-1],[])


if __name__=='__main__':unittest.main(verbosity=2)
