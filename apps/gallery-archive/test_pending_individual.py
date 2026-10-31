import copy
import unittest
from load_pending_individual import load


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


if __name__=='__main__':unittest.main(verbosity=2)
