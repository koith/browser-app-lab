import hashlib, io, json, tempfile, zipfile
from pathlib import Path
from PIL import Image
from ingest_verified_zips import build

with tempfile.TemporaryDirectory() as temp:
    root=Path(temp)
    source=root/'album.zip'
    photos=[]
    with zipfile.ZipFile(source,'w') as z:
        for n in range(1,4):
            im=Image.new('RGB',(900+n,1300+n),(n*47,n*23,n*19))
            stream=io.BytesIO(); im.save(stream,format='PNG')
            content=stream.getvalue()
            name=f'{n:03d}.png'
            z.writestr('images/'+name,content)
            photos.append({'n':n,'file':name,'sha256':hashlib.sha256(content).hexdigest()})
        z.writestr('manifest.json',json.dumps({'id':'sample-album','title':'Sample','advertised_count':3,'images':photos}))
    out=root/'stage'
    result=build([source],out)
    album=result['albums'][0]
    assert album['stored']==3 and album['complete_sequence']
    for photo in album['images']:
        local=out/photo['key']
        thumb=out/photo['preview']
        assert local.is_file() and thumb.is_file()
        assert hashlib.sha256(local.read_bytes()).hexdigest()==photo['sha256']
        assert thumb.stat().st_size==photo['preview_bytes']
        assert hashlib.sha256(thumb.read_bytes()).hexdigest()==photo['preview_sha256']
        with Image.open(thumb) as im:assert im.width<=520
    assert result['storage_provider']=='pending_external_upload'
    assert (out/'metadata/catalog.json').is_file()
    print('CLOUD_INGEST_TEST_PASS',album['stored'])
