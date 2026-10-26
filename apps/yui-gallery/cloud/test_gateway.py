import json, os
os.environ['GALLERY_ACCESS_TOKEN']='test-gallery-token'
os.environ['RCLONE_CONFIG_ARCHIVE_COOKIE']='fake-local-test-cookie'
from fastapi.testclient import TestClient
from gateway import main as gateway

catalog={'schema_version':1,'albums':[{'id':'test-album','title':'Sample',
 'images':[{'number':1,'key':'originals/test-album/0001.jpg',
            'preview':'previews/test-album/0001.jpg','width':900,'height':1350}]}]}
async def fake_read(key,limit):
    if key=='metadata/catalog.json':return json.dumps(catalog).encode()
    if key in ('originals/test-album/0001.jpg','previews/test-album/0001.jpg'):return b'test-binary-photo'
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
        assert response.content==b'test-binary-photo'
    assert client.get('/api/media/unknown/1/original',headers=header).status_code==404
    assert client.get('/api/media/test-album/1/wrong',headers=header).status_code==404
print('AUTHENTICATED_GATEWAY_TEST_PASS')
