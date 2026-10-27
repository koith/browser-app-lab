"""Registration must preserve existing works and reject changed image bytes."""
import json,tempfile,hashlib
from pathlib import Path
from PIL import Image
from build_additional_source_manifest import build
with tempfile.TemporaryDirectory() as tmp:
    root=Path(tmp);out=root/'gallery.json'
    for aid,color in [('album-one',(1,2,3)),('album-two',(4,5,6))]:
        folder=root/aid;folder.mkdir();photo=folder/'1.jpg';Image.new('RGB',(600,900),color).save(photo)
        blob=photo.read_bytes();(folder/'manifest.json').write_text(json.dumps({'id':aid,'title':aid,'expected':1,'images':[{'number':1,'file':'1.jpg','url':'https://wes.misskon.com/images/visible.jpg','bytes':len(blob),'sha256':hashlib.sha256(blob).hexdigest(),'width':600,'height':900}]}))
        build([folder],out)
    assert {a['id'] for a in json.loads(out.read_text())['albums']}=={'album-one','album-two'}
    # A large pixel count must never close the highest-resolution investigation.
    manifest=json.loads((folder/'manifest.json').read_text())
    Image.new('RGB',(2200,3300),(7,8,9)).save(photo)
    raw=photo.read_bytes();manifest['images'][0].update(bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest(),width=2200,height=3300)
    (folder/'manifest.json').write_text(json.dumps(manifest));build([folder],out)
    registered=next(a for a in json.loads(out.read_text())['albums'] if a['id']=='album-two')
    assert registered['resolution_review_required'] and not registered['publisher_original_verified']
    assert registered['highest_resolution_status'].startswith('unverified')
    before=out.read_bytes();photo.write_bytes(b'changed')
    try:build([folder],out)
    except ValueError:pass
    else:raise AssertionError('Tampered photo registered')
    assert out.read_bytes()==before,'Failed registration damaged an existing gallery'
print('AUTOMATIC_REGISTRATION_PRESERVES_ALL_WORKS_AND_REJECTS_TAMPERING_PASS')
