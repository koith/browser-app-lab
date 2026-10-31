"""Private queue admission binds exact readback objects and survives publication later."""
import hashlib
from io import BytesIO
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from PIL import Image

import defer_verified_batch as deferred
from load_pending_individual import load
import verify_terabox


class DeferredBatchTests(unittest.TestCase):
    def setUp(self):
        self.tmp=TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.stage=Path(self.tmp.name);(self.stage/'metadata').mkdir()
        self.owner={'schema_version':1,'model':'mimmi','albums':[{'id':'saved-work',
            'title':'Saved work','images':[{'number':10,'sha256':'a'*64}]}]}
        original=BytesIO();Image.new('RGB',(400,600),'blue').save(original,'JPEG')
        preview=BytesIO()
        Image.frombytes('RGB',(200,300),bytes((i*37+i//11)%256 for i in range(200*300*3))).save(
            preview,'WEBP',lossless=True)
        raw=original.getvalue();thumb=preview.getvalue()
        self.photo={'number':11,'key':'originals/saved-work/11-new.jpg',
            'sha256':hashlib.sha256(raw).hexdigest(),'bytes':len(raw),'width':400,'height':600,
            'preview':'previews/saved-work/11-new.webp','preview_bytes':len(thumb),
            'preview_sha256':hashlib.sha256(thumb).hexdigest(),'source_photo_number':27,
            'work_identity_saved_cut_anchors':10,'higher_resolution_replacement':False}
        for key,data in [(self.photo['key'],raw),(self.photo['preview'],thumb)]:
            p=self.stage/key;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(data)
        self.original_bytes=raw
        self.write('catalog.json',{'schema_version':1,'model':'mimmi','albums':[
            {'id':'saved-work','title':'Saved work','images':[self.photo]}]})
        self.write('collection-audit.json',{'results':[{'id':'saved-work',
            'source_edition_all_files_accounted_for':True,'known_web_edition_photos':27,
            'source_files_decoded':27,'unresolved_source_numbers':[]}]})

    def write(self,name,data):
        (self.stage/'metadata'/name).write_text(json.dumps(data))

    def readback_proof(self):
        with patch.object(verify_terabox,'read_remote_with_recovery',side_effect=lambda row,remote:row[0]) as reader:
            report=verify_terabox.verify(self.stage,'archive:MimmiArchive',1,only_staged=True)
        self.assertEqual(reader.call_count,2)
        self.assertEqual(report['media_checked'],2)
        return report

    def test_roundtrip_retains_original_bytes_and_requires_a_later_independent_admission(self):
        doc=deferred.prepare(self.stage,self.owner);photo=doc['albums'][0]['images'][0]
        self.assertEqual((self.stage/photo['key']).read_bytes(),self.original_bytes)
        self.assertEqual(photo['key'],'originals/saved-work/'+photo['sha256']+'.jpg')
        self.assertEqual(photo['preview'],'previews/saved-work/'+photo['preview_sha256']+'.webp')
        with self.assertRaises(FileNotFoundError):deferred.verified_queue(self.stage)
        self.readback_proof();pin,raw=deferred.verified_queue(self.stage)
        admitted,batches=load(self.owner,[(pin+'.json',json.loads(raw))],'mimmi')
        result=admitted['albums'][0]['images'][0]
        self.assertEqual((result['number'],result['source_photo_number']),(11,27))
        self.assertEqual(result['numbering_provenance'],'archive_append_order_not_publisher_number')
        self.assertEqual(result['sha256'],photo['sha256'])
        self.assertEqual(batches,[pin])

    def test_unidentified_replacement_or_unspecified_coverage_never_enters_deferred_queue(self):
        doc=json.loads((self.stage/'metadata/catalog.json').read_text())
        doc['albums'][0]['images'][0]['work_identity_saved_cut_anchors']=2
        self.write('catalog.json',doc)
        with self.assertRaises(ValueError):deferred.prepare(self.stage,self.owner)
        doc['albums'][0]['images'][0]['work_identity_saved_cut_anchors']=10
        doc['albums'][0]['images'][0]['higher_resolution_replacement']=True
        self.write('catalog.json',doc)
        with self.assertRaises(ValueError):deferred.prepare(self.stage,self.owner)
        doc['albums'][0]['images'][0]['higher_resolution_replacement']=False
        self.write('catalog.json',doc)
        self.write('collection-audit.json',{'results':[{'id':'saved-work',
            'source_edition_all_files_accounted_for':False}]})
        with self.assertRaises(ValueError):deferred.prepare(self.stage,self.owner)

    def test_good_files_from_partial_edition_keep_the_exact_unresolved_numbers(self):
        self.write('collection-audit.json',{'results':[{'id':'saved-work',
            'source_edition_all_files_accounted_for':False,'known_web_edition_photos':27,
            'source_files_decoded':26,'unresolved_source_numbers':[26]}]})
        deferred.prepare(self.stage,self.owner);self.readback_proof()
        _,raw=deferred.verified_queue(self.stage)
        coverage=json.loads(raw)['albums'][0]['source_coverage']
        self.assertFalse(coverage['source_edition_all_files_accounted_for'])
        self.assertEqual(coverage['unresolved_source_numbers'],[26])
        self.write('collection-audit.json',{'results':[{'id':'saved-work',
            'source_edition_all_files_accounted_for':False,'known_web_edition_photos':27,
            'source_files_decoded':26,'unresolved_source_numbers':[27]}]})
        with self.assertRaises(ValueError):deferred.prepare(self.stage,self.owner)

    def test_equal_readback_counts_cannot_acknowledge_different_objects_or_failed_media(self):
        deferred.prepare(self.stage,self.owner);report=self.readback_proof()
        for change in [{'verified_specs_sha256':'b'*64},{'failed':1},{'full_SHA256_verified':1}]:
            self.write('remote-verification.json',{**report,**change})
            with self.assertRaises(ValueError):deferred.verified_queue(self.stage)

    def test_changed_dimensions_and_files_are_rejected_after_remote_acknowledgement(self):
        doc=deferred.prepare(self.stage,self.owner);self.readback_proof()
        doc['albums'][0]['images'][0]['width']=401
        self.write('deferred-delta.json',doc)
        with self.assertRaises(ValueError):deferred.verified_queue(self.stage)
        doc['albums'][0]['images'][0]['width']=400
        self.write('deferred-delta.json',doc)
        (self.stage/doc['albums'][0]['images'][0]['key']).write_bytes(b'corrupted')
        with self.assertRaises(ValueError):deferred.verified_queue(self.stage)

    def test_private_queue_must_read_back_byte_for_byte_without_a_live_catalog_write(self):
        deferred.prepare(self.stage,self.owner);self.readback_proof()
        pin,raw=deferred.verified_queue(self.stage)
        with patch.object(deferred.subprocess,'run',side_effect=[SimpleNamespace(stdout=b''),
                SimpleNamespace(stdout=b'corrupted-queue')]) as run:
            with self.assertRaises(ValueError):deferred.persist(self.stage,'archive:MimmiArchive')
        destinations=[call.args[0] for call in run.call_args_list]
        self.assertTrue(all('metadata/pending-individual/mimmi/'+pin+'.json' in ' '.join(cmd) for cmd in destinations))
        self.assertTrue(all('metadata/catalog.json' not in ' '.join(cmd) for cmd in destinations))


if __name__=='__main__':unittest.main(verbosity=2)
