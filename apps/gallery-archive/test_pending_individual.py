import copy
import json
import sys
import unittest
from load_pending_individual import load,storage,accessible_documents
from read_owner_metadata import ProviderVerificationRequired


class PendingTests(unittest.TestCase):
    def setUp(self):
        self.row={'number':1,'sha256':'a'*64,'bytes':10000,'width':400,'height':600,
            'preview_sha256':'b'*64,'preview_bytes':2000,
            'key':'originals/saved-work/'+'a'*64+'.jpg','preview':'previews/saved-work/'+'b'*64+'.webp',
            'source_photo_number':17,'work_identity_saved_cut_anchors':3}
        self.owner={'schema_version':1,'model':'mimmi','albums':[{'id':'saved-work','title':'Work','images':[
            {**self.row,'number':9,'sha256':'c'*64}]}]}
        self.queue={'schema_version':1,'model':'mimmi','source_batch_sha256':'d'*64,
                    'albums':[{'id':'saved-work','images':[self.row]}]}

    def test_append_after_fresh_inventory_and_skip_exact_duplicates(self):
        delta,_=load(self.owner,[('d'*64+'.json',self.queue)],'mimmi')
        p=delta['albums'][0]['images'][0];self.assertEqual(p['number'],10)
        self.assertEqual(p['source_photo_number'],17);self.assertEqual(self.owner['albums'][0]['images'][0]['number'],9)
        current=copy.deepcopy(self.owner);current['albums'][0]['images'].append(p)
        self.assertEqual(load(current,[('d'*64+'.json',self.queue)],'mimmi')[0]['albums'],[])

    def test_wrong_work_path_correspondence_and_model_fail_closed(self):
        for field,value in [('key','originals/saved-work/../../metadata/catalog.json'),
                            ('preview','previews/saved-work/other.webp'),('work_identity_saved_cut_anchors',2)]:
            q=copy.deepcopy(self.queue);q['albums'][0]['images'][0][field]=value
            with self.subTest(field=field):
                with self.assertRaises(ValueError):load(self.owner,[('d'*64+'.json',q)],'mimmi')
        with self.assertRaises(ValueError):load(self.owner,[('../invalid',self.queue)],'mimmi')
        with self.assertRaises(ValueError):load(self.owner,[('d'*64+'.json',self.queue)],'yui')

    def test_provider_error_is_not_admitted_and_diagnostic_does_not_expose_payload(self):
        for bad in [{'errno':-9,'errmsg':'private-cookie-must-not-be-logged'},
                    {**self.queue,'source_batch_sha256':'e'*64},[]]:
            with self.assertRaises(ValueError) as error:load(self.owner,[('d'*64+'.json',bad)],'mimmi')
            self.assertIn('queue_prefix',str(error.exception))
            self.assertNotIn('private-cookie',str(error.exception))
            self.assertNotIn('originals/',str(error.exception))

    def test_full_metadata_stream_is_bounded_and_preserves_exact_response(self):
        command=[sys.executable,'-c',"import sys;sys.stdout.buffer.write(b'full-individual-json')"]
        self.assertEqual(storage([],limit=64,command=command),b'full-individual-json')
        with self.assertRaises(ValueError):storage([],limit=4,command=command)

    def test_challenged_queue_is_retained_without_blocking_an_independent_good_queue(self):
        entries=[{'Path':digest*64+'.json','Size':1000} for digest in ['e','d']]
        calls=[]
        def reader(remote,model,*,batch):
            calls.append(batch)
            if batch=='e'*64:raise ProviderVerificationRequired('400141')
            return json.dumps(self.queue).encode()
        documents,held=accessible_documents(entries,'archive:MimmiArchive','mimmi',reader)
        self.assertEqual(held,1);self.assertEqual(calls,['e'*64,'d'*64])
        delta,_=load(self.owner,documents,'mimmi')
        self.assertEqual(len(delta['albums'][0]['images']),1)
        def malformed(*a,**kw):raise ValueError('wrong model or corrupt metadata')
        with self.assertRaises(ValueError):accessible_documents(entries,'archive:MimmiArchive','mimmi',malformed)


if __name__=='__main__':unittest.main(verbosity=2)
