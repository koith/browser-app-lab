import asyncio
import hashlib
import json
import os
import tempfile
from pathlib import Path

os.environ['GALLERY_ACCESS_TOKEN']='test-gallery-token'
os.environ['RCLONE_CONFIG_ARCHIVE_COOKIE']='fake-local-test-cookie'
from fastapi.testclient import TestClient
from fastapi import HTTPException
from gateway import main as gateway

# A real subprocess must be drained across multiple stdout/stderr chunks.
with tempfile.TemporaryDirectory() as tmp:
    fake_rclone=Path(tmp)/'rclone'
    fake_rclone.write_text(
        "#!/usr/bin/env python3\n"
        "import sys\n"
        "sys.stdout.buffer.write(b'A' * 196608)\n"
        "sys.stdout.buffer.flush()\n"
        "sys.stderr.buffer.write(b'warning' * 12000)\n"
    )
    fake_rclone.chmod(0o755)
    original_path=os.environ.get('PATH','')
    os.environ['PATH']=tmp+os.pathsep+original_path
    try:
        result=asyncio.run(gateway.rclone_bytes('test/big.jpg',200000))
        assert result==b'A'*196608,(len(result),'partial read')
        try:
            asyncio.run(gateway.rclone_bytes('test/big.jpg',100))
            raise AssertionError('Oversize remote read accepted')
        except HTTPException as exc:
            assert exc.status_code==413
    finally:
        os.environ['PATH']=original_path

photo=b'test-binary-photo'
digest=hashlib.sha256(photo).hexdigest()
catalog={'schema_version':1,'albums':[{'id':'test-album','title':'Sample',
 'images':[{'number':1,'key':'originals/test-album/0001.jpg',
            'preview':'previews/test-album/0001.jpg','width':900,'height':1350,
            'bytes':len(photo),'sha256':digest,
            'preview_bytes':len(photo),'preview_sha256':digest}]}]}
async def fake_read(key,limit):
    if key=='metadata/catalog.json':return json.dumps(catalog).encode()
    if key in ('originals/test-album/0001.jpg','previews/test-album/0001.jpg'):return photo
    raise ValueError('Unexpected storage read')
gateway.rclone_bytes=fake_read

with TestClient(gateway.app) as client:
    assert client.get('/api/health').status_code==200
    assert client.get('/api/catalog').status_code==401
    header={'Authorization':'Bearer test-gallery-token'}
    assert client.get('/api/catalog',headers=header).json()['albums'][0]['id']=='test-album'
    for kind in ('preview','original'):
        response=client.get('/api/media/test-album/1/'+kind,headers=header)
        assert response.status_code==200
        assert response.content==photo
        assert int(response.headers['content-length'])==len(photo)
    assert client.get('/api/media/unknown/1/original',headers=header).status_code==404
    assert client.get('/api/media/test-album/1/wrong',headers=header).status_code==404

    async def corrupted_read(key,limit):
        if key.startswith('originals/'):
            return b'tampered-same-len'  # matching byte count alone cannot pass
        return await fake_read(key,limit)
    gateway.rclone_bytes=corrupted_read
    response=client.get('/api/media/test-album/1/original',headers=header)
    assert response.status_code==502 and 'integrity' in response.json()['detail'].lower()

print('AUTHENTICATED_GATEWAY_TEST_PASS')
