#!/usr/bin/env python3
"""Offline integration QA for the byte-exact remote TeraBox readback protocol."""
import hashlib
import io
import json
import os
import shutil
import tempfile
import zipfile
from pathlib import Path

from PIL import Image
from ingest_verified_zips import build
from verify_remote import verify_catalog, verify_media

with tempfile.TemporaryDirectory() as temp:
    root=Path(temp)
    archive=root/'test.zip'
    entries=[]
    with zipfile.ZipFile(archive,'w') as z:
        for n in (1,2):
            im=Image.new('RGB',(901+n,1301+n),(n*30,n*60,n*80))
            fp=io.BytesIO()
            im.save(fp,format='PNG')
            blob=fp.getvalue()
            filename=f'{n:03}.png'
            z.writestr('images/'+filename,blob)
            entries.append({'number':n,'file':filename,'sha256':hashlib.sha256(blob).hexdigest()})
        z.writestr('manifest.json',json.dumps(
            {'id':'sample-album','title':'Sample','advertised_count':2,'images':entries}))
    stage=root/'stage'
    catalog=build([archive],stage)
    mirror=root/'mirror'
    shutil.copytree(stage,mirror)
    fakebin=root/'bin'
    fakebin.mkdir()
    fake=fakebin/'rclone'
    fake.write_text(
        '#!/usr/bin/env python3\n'
        'import os,sys\n'
        'from pathlib import Path\n'
        'key=sys.argv[2]\n'
        'prefix="archive:YuiArchive/"\n'
        'if not key.startswith(prefix): sys.exit(3)\n'
        'p=Path(os.environ["MOCK_RCLONE_ROOT"])/key[len(prefix):]\n'
        'if not p.is_file(): sys.exit(4)\n'
        'sys.stdout.buffer.write(p.read_bytes())\n'
    )
    fake.chmod(0o755)
    old_path=os.environ.get('PATH','')
    os.environ['PATH']=str(fakebin)+os.pathsep+old_path
    os.environ['MOCK_RCLONE_ROOT']=str(mirror)
    try:
        report=verify_media(stage,'archive:YuiArchive',workers=2)
        assert report['originals']==2 and report['media_files']==4
        assert len(report['remote_retrievals'])==4
        assert (stage/'metadata/remote-verification.json').is_file()

        # The upload script publishes the verified catalogue only after the images.
        cat=stage/'metadata/catalog.json'
        data=json.loads(cat.read_text())
        data['storage_provider']='terabox'
        cat.write_text(json.dumps(data))
        shutil.copy2(cat,mirror/'metadata/catalog.json')
        verify_catalog(stage,'archive:YuiArchive')

        preview=mirror/catalog['albums'][0]['images'][0]['preview']
        before=preview.read_bytes()
        preview.write_bytes(b'X'+before[1:])  # unchanged length, incorrect SHA
        try:
            verify_media(stage,'archive:YuiArchive',workers=2)
            raise AssertionError('Accepted a remote image altered without changing its size')
        except ValueError as error:
            assert 'Remote byte/hash mismatch' in str(error)
        preview.write_bytes(before)

        (mirror/'metadata/catalog.json').write_text('{}')
        try:
            verify_catalog(stage,'archive:YuiArchive')
            raise AssertionError('Accepted an incorrect remote catalogue')
        except ValueError as error:
            assert 'Remote catalogue differs' in str(error)
    finally:
        os.environ['PATH']=old_path
        os.environ.pop('MOCK_RCLONE_ROOT',None)
print('REMOTE_READBACK_SHA256_TEST_PASS')
