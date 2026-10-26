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
    before=out.read_bytes();photo.write_bytes(b'changed')
    try:build([folder],out)
    except ValueError:pass
    else:raise AssertionError('Tampered photo registered')
    assert out.read_bytes()==before,'Failed registration damaged an existing gallery'
print('AUTOMATIC_REGISTRATION_PRESERVES_ALL_WORKS_AND_REJECTS_TAMPERING_PASS')
