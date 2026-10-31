import copy
import hashlib
import unittest
from pathlib import Path
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

from sealed_work_metadata import encode,metadata_only,validate,seal,unseal


class SealedMetadataTests(unittest.TestCase):
    def setUp(self):
        import json
        root=Path(__file__).resolve().parents[2]
        self.reviewed={a['id']:a for a in json.loads((root/'apps/mimmi-gallery/public-work-pages.json').read_text())['albums']}
        aid='v2ph-actor-z63984ma';total=self.reviewed[aid]['public_web_edition_photos']
        digest=lambda n:hashlib.sha256(str(n).encode()).hexdigest()
        self.owner={'schema_version':1,'model':'mimmi','albums':[{'id':aid,'images':[
            {'number':n,'sha256':digest(n)} for n in (1,2,3)]}]}
        coverage={'source':self.reviewed[aid]['source'],'known_web_edition_photos':total,
            'observed_filename_numbers':list(range(1,total+1)),'source_files_decoded':total,
            'source_edition_all_files_accounted_for':True,'unresolved_source_numbers':[],
            'uncertain_source_numbers':[],'saved_cut_correspondence':[
                {'source_file_number':n,'owner_archive_number':n,'owner_sha256':digest(n),
                 'source_sha256':digest(n),'whole_frame_visual_error':0.1} for n in (1,2,3)]}
        images=[{'sha256':digest(n),'bytes':9000,'width':600,'height':900,'extension':'jpg',
            'preview_sha256':digest(n+1000),'preview_bytes':5000,'preview_width':400,'preview_height':600,
            'source_photo_number':n,'work_identity_saved_cut_anchors':3} for n in range(4,total+1)]
        self.data={'schema_version':1,'metadata_only':True,'model':'mimmi',
            'albums':[{'id':aid,'source_coverage':coverage,'images':images}]}

    def test_source_numbering_exact_owner_anchors_and_metadata_only_fields_are_required(self):
        self.assertEqual(validate(self.data,self.owner,self.reviewed),self.data)
        for change in ['wrong_model','unknown_work','wrong_anchor','duplicate_number','extra_image_bytes','incomplete_source']:
            d=copy.deepcopy(self.data);a=d['albums'][0]
            if change=='wrong_model':d['model']='yui'
            if change=='unknown_work':a['id']='unreviewed-work'
            if change=='wrong_anchor':a['source_coverage']['saved_cut_correspondence'][0]['owner_sha256']='f'*64
            if change=='duplicate_number':a['images'][1]['source_photo_number']=a['images'][0]['source_photo_number']
            if change=='extra_image_bytes':a['images'][0]['image_base64']='forbidden-image-content'
            if change=='incomplete_source':a['source_coverage']['observed_filename_numbers'].pop()
            with self.subTest(change=change),self.assertRaises(ValueError):validate(d,self.owner,self.reviewed)

    def test_only_bound_metadata_can_be_decrypted_by_the_running_recipient(self):
        key=rsa.generate_private_key(public_exponent=65537,key_size=2048);raw=encode(self.data)
        recipient={'repository':'koith/browser-app-lab','model':'mimmi','run_id':123,'attempt':1,
            'metadata_sha256':hashlib.sha256(raw).hexdigest(),'public_key_pem':key.public_key().public_bytes(
                serialization.Encoding.PEM,serialization.PublicFormat.SubjectPublicKeyInfo).decode()}
        envelope=seal(raw,recipient)
        self.assertEqual(unseal(envelope,recipient,key),self.data)
        self.assertNotIn('source_file_number',encode(envelope).decode())
        with self.assertRaises(ValueError):seal(encode({**self.data,'image_base64':'forbidden'}),recipient)
        for name in ['run_id','attempt','metadata_sha256']:
            wrong={**recipient,name:('f'*64 if name=='metadata_sha256' else 999)}
            with self.subTest(field=name),self.assertRaises(ValueError):unseal(envelope,wrong,key)
        bad={**envelope,'ciphertext':envelope['ciphertext'][:-4]+'AAAA'}
        with self.assertRaises(Exception):unseal(bad,recipient,key)


if __name__=='__main__':unittest.main(verbosity=2)
