"""A stale source or renamed wrong-model image must not reenter the gallery."""
import hashlib,json,tempfile
from pathlib import Path
from unittest.mock import patch
from PIL import Image
import identity_policy
from build_additional_source_manifest import build
with tempfile.TemporaryDirectory() as tmp:
 root=Path(tmp);folder=root/'incoming';folder.mkdir();file=folder/'photo.jpg';Image.new('RGB',(600,900),(20,40,80)).save(file);raw=file.read_bytes();digest=hashlib.sha256(raw).hexdigest()
 image={'number':1,'file':'photo.jpg','url':'https://wes.misskon.com/images/photo.jpg','bytes':len(raw),'sha256':digest,'width':600,'height':900}
 base={'id':'safe-album','title':'Safe fixture','expected':1,'source_pages':['https://example.com/allowed'],'images':[image]}
 policy=root/'policy.json';out=root/'gallery.json';out.write_text(json.dumps({'albums':[]}));before=out.read_bytes()
 empty={'excluded_album_ids':[],'excluded_source_ids':[],'excluded_source_urls':[],'excluded_image_sha256':[]}
 for key,value in [('excluded_album_ids','safe-album'),('excluded_source_urls','https://example.com/allowed'),('excluded_image_sha256',digest)]:
  p={**empty,key:[value]};policy.write_text(json.dumps(p));(folder/'manifest.json').write_text(json.dumps(base))
  with patch.object(identity_policy,'POLICY',policy):
   try:build([folder],out)
   except ValueError as e:assert 'identity policy' in str(e)
   else:raise AssertionError('Excluded content was registered')
  assert out.read_bytes()==before,'Rejected content changed the public gallery'
 policy.write_text(json.dumps(empty))
 with patch.object(identity_policy,'POLICY',policy):build([folder],out)
 assert json.loads(out.read_text())['albums'][0]['id']=='safe-album'
print('IDENTITY_POLICY_BLOCKS_STALE_SOURCE_AND_RENAMED_IMAGES_PASS')
