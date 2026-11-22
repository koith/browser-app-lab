"""Real decoded image fixtures for partial verified owner photo transfers."""
from io import BytesIO
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from PIL import Image
from upload_verified_individual import persist_new_photos,durable_pair_checkpoint


def picture(seed,fmt):
    im=Image.new('RGB',(400,600))
    im.putdata([((x+seed*3)%255,(y+seed)%255,(x+y+seed*17)%255)
                for y in range(600) for x in range(400)])
    data=BytesIO();im.save(data,format=fmt)
    return data.getvalue()


class SinglePhotoUploadTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.stage=Path(self.tmp.name)/'stage'
        (self.stage/'metadata').mkdir(parents=True)
        self.model='mimmi'
        self.remote='archive:MimmiArchive'
        old_data=picture(1,'JPEG')
        digest=hashlib.sha256(old_data).hexdigest()
        self.old={'number':1,'key':'originals/work/00001-old.jpg',
                  'sha256':digest,'bytes':len(old_data),
                  'width':400,'height':600,
                  'preview':'previews/work/00001-old.webp',
                  'preview_sha256':'b'*64,'preview_bytes':2000}
        self.old_catalog={'schema_version':1,'model':self.model,
                          'storage':'owner-private-terabox-sha-verified-bytes',
                          'albums':[{'id':'work','title':'Mimmi test',
                                     'images':[self.old]}]}
        self.before=Path(self.tmp.name)/'owner-before.json'
        self.before.write_text(json.dumps(self.old_catalog))
        self.photos=[]
        for n in (2,3):
            raw=picture(n*3,'JPEG')
            thumb=picture(n*3,'WEBP')
            sha=hashlib.sha256(raw).hexdigest()
            thumb_sha=hashlib.sha256(thumb).hexdigest()
            row={'number':n,'key':f'originals/work/{n:05d}-{sha[:16]}.jpg',
                 'sha256':sha,'bytes':len(raw),'width':400,'height':600,
                 'preview':f'previews/work/{n:05d}-{thumb_sha[:16]}.webp',
                 'preview_sha256':thumb_sha,'preview_bytes':len(thumb)}
            self.photos.append(row)
            for key,data in [(row['key'],raw),(row['preview'],thumb)]:
                p=self.stage/key;p.parent.mkdir(parents=True,exist_ok=True)
                p.write_bytes(data)
        self.catalog={**self.old_catalog,'albums':[{'id':'work',
                      'title':'Mimmi test','images':[self.old]+self.photos}]}
        (self.stage/'metadata/catalog.json').write_text(json.dumps(self.catalog))

    def test_partial_remote_failure_does_not_destroy_other_verified_pair(self):
        remote_bytes={}
        denied=self.photos[0]['preview']
        def upload(args):
            target=args[2].removeprefix(self.remote+'/')
            if target==denied:
                return 4
            remote_bytes[target]=Path(args[1]).read_bytes()
            return 0
        def read(row,remote):
            key,size,sha=row
            data=remote_bytes.get(key)
            if data is None or len(data)!=size or hashlib.sha256(data).hexdigest()!=sha:
                raise ValueError('Missing verified exact bytes')
            return key
        report=persist_new_photos(self.stage,self.before,self.remote,
                                self.model,uploader=upload,readback=read,sleep=lambda n:None)
        self.assertEqual(report['new_photo_pairs_sha_verified'],1,report)
        self.assertEqual(report['failed_photo_pairs'],1)
        self.assertEqual(report['new_photos'],1)
        merged=json.loads((self.stage/'metadata/catalog.json').read_text())
        self.assertEqual([p['number'] for p in merged['albums'][0]['images']],[1,3])
        self.assertTrue((self.stage/self.photos[1]['key']).is_file())
        self.assertTrue((self.stage/self.photos[1]['preview']).is_file())
        self.assertFalse((self.stage/self.photos[0]['key']).exists())
        self.assertFalse((self.stage/self.photos[0]['preview']).exists())
        for key in ('key','preview'):
            saved=self.stage/'held-upload-files'/self.photos[0][key]
            self.assertTrue(saved.is_file(),key)
            self.assertEqual(hashlib.sha256(saved.read_bytes()).hexdigest(),
                             self.photos[0]['sha256' if key=='key' else 'preview_sha256'])

    def test_client_success_without_correct_sha_cannot_publish(self):
        def uploader(args):
            return 0
        def wrong(row,remote):
            raise ValueError('SHA mismatch')
        with self.assertRaisesRegex(ValueError,'No independently verified'):
            persist_new_photos(self.stage,self.before,self.remote,self.model,
                               uploader=uploader,readback=wrong,sleep=lambda n:None)
        self.assertEqual(json.loads((self.stage/'metadata/catalog.json').read_text()),
                         self.catalog)

    def test_blocking_one_original_does_not_revoke_another_photo(self):
        remote_bytes={}
        blocked=self.photos[0]['key']
        def uploader(args):
            key=args[2].removeprefix(self.remote+'/')
            if key==blocked:
                return 1
            remote_bytes[key]=Path(args[1]).read_bytes()
            return 0
        def reader(row,remote):
            key,n,sha=row
            raw=remote_bytes.get(key)
            if raw is None or len(raw)!=n or hashlib.sha256(raw).hexdigest()!=sha:
                raise ValueError('Missing exact remote data')
            return key
        data=persist_new_photos(self.stage,self.before,self.remote,self.model,
                                uploader=uploader,readback=reader,sleep=lambda n:None)
        self.assertEqual((data['new_photos'],data['failed_photo_pairs']),(1,1))
        self.assertEqual(data['held_failure_reasons'],{'upload_rejected':1})

    def test_budget_stop_keeps_verified_pair_and_durable_receipt(self):
        remote_bytes={}
        def upload(args):
            remote_bytes[args[2]]=Path(args[1]).read_bytes()
            return 0
        def reader(row,remote):
            key,size,sha=row
            raw=remote_bytes[remote+'/'+key]
            if len(raw)!=size or hashlib.sha256(raw).hexdigest()!=sha:
                raise ValueError('wrong bytes')
            return key
        receipts=[]
        def exact_receipt(stage,target,raw):
            self.assertEqual(remote_bytes[target],raw)
            receipts.append(json.loads(raw))
        def checkpoint(album,row):
            durable_pair_checkpoint(self.stage,self.remote,self.model,'123-1',
                                    album,row,upload,exact_receipt)
        report=persist_new_photos(self.stage,self.before,self.remote,self.model,
            uploader=upload,readback=reader,sleep=lambda n:None,
            checkpoint=checkpoint,stop_before=lambda:bool(receipts))
        self.assertEqual(report['new_photos'],1)
        self.assertEqual(report['durable_pair_checkpoints'],1)
        self.assertTrue(report['stopped_to_preserve_commit_budget'])
        self.assertEqual(len(receipts),1)
        self.assertEqual(receipts[0]['photo']['sha256'],self.photos[0]['sha256'])
        self.assertIn(self.remote+'/'+self.photos[0]['key'],remote_bytes)
        self.assertNotIn(self.remote+'/'+self.photos[1]['key'],remote_bytes)
        saved=json.loads((self.stage/'metadata/catalog.json').read_text())
        self.assertEqual([p['number'] for p in saved['albums'][0]['images']],[1,2])

    def test_runner_interruption_leaves_earlier_remote_pair_receipt(self):
        remote_bytes={}
        def upload(args):
            if args[2]==self.remote+'/'+self.photos[1]['key']:
                raise KeyboardInterrupt()
            remote_bytes[args[2]]=Path(args[1]).read_bytes()
            return 0
        def reader(row,remote):
            key,size,sha=row
            raw=remote_bytes[remote+'/'+key]
            self.assertEqual((len(raw),hashlib.sha256(raw).hexdigest()),(size,sha))
            return key
        def checkpoint(album,row):
            def exact(stage,target,raw):
                self.assertEqual(remote_bytes[target],raw)
            durable_pair_checkpoint(self.stage,self.remote,self.model,'124-1',
                                    album,row,upload,exact)
        with self.assertRaises(KeyboardInterrupt):
            persist_new_photos(self.stage,self.before,self.remote,self.model,
                uploader=upload,readback=reader,sleep=lambda n:None,checkpoint=checkpoint)
        saved=[json.loads(raw) for key,raw in remote_bytes.items()
               if '/metadata/verified-pair-checkpoints/' in key]
        self.assertEqual(len(saved),1)
        self.assertEqual(saved[0]['photo']['sha256'],self.photos[0]['sha256'])
        self.assertIn(self.remote+'/'+self.photos[0]['preview'],remote_bytes)
        self.assertNotIn(self.remote+'/'+self.photos[1]['key'],remote_bytes)

    def test_wrong_remote_and_missing_local_pair_hard_fail(self):
        with self.assertRaisesRegex(ValueError,'Wrong owner archive'):
            persist_new_photos(self.stage,self.before,'archive:YuiArchive',
                               self.model,uploader=lambda args:0)
        (self.stage/self.photos[0]['preview']).unlink()
        with self.assertRaisesRegex(ValueError,'Incomplete locally staged'):
            persist_new_photos(self.stage,self.before,self.remote,
                               self.model,uploader=lambda args:0)


if __name__=='__main__':
    unittest.main(verbosity=2)
