"""New SHA URLs refresh stale catalogues and never serve older photo bytes."""
import hashlib
import json
import os
import time
from copy import deepcopy

os.environ['GALLERY_ACCESS_TOKEN']='offline-token'
os.environ['RCLONE_CONFIG_ARCHIVE_COOKIE']='offline-cookie'
from fastapi.testclient import TestClient
from gateway import main as gateway

old=b'previous-original'*1000
new=b'new-higher-resolution-original'*1000
sha=lambda value:hashlib.sha256(value).hexdigest()

def catalog(model,data):
    return {'schema_version':1,'model':model,'albums':[{'id':'saved-album','images':[{
        'number':1,'key':'originals/saved-album/'+sha(data)+'.jpg',
        'bytes':len(data),'sha256':sha(data)}]}]}

reads=[]
async def remote(key,limit,*,remote=None):
    model='yui' if remote==gateway.YUI_REMOTE else 'mimmi';reads.append((model,key))
    if key=='metadata/catalog.json':return json.dumps(catalog(model,new)).encode()
    if key=='originals/saved-album/'+sha(new)+'.jpg':return new
    raise AssertionError('An older object must never be read under a newer SHA URL')

gateway.rclone_bytes=remote
with TestClient(gateway.app) as client:
    for model,cache in [('mimmi',gateway._cache),('yui',gateway._yui_cache)]:
        cache.update(catalog=catalog(model,old),time=time.time())
        prefix='/api/yui' if model=='yui' else '/api'
        url=prefix+'/media/saved-album/1/original?v='
        reply=client.get(url+sha(new))
        assert reply.status_code==200 and reply.content==new,(model,reply.status_code)
        assert reply.headers['etag']=='"'+sha(new)+'"'
        assert sum(m==model and key=='metadata/catalog.json' for m,key in reads)==1
        missing=client.get(url+'f'*64)
        assert missing.status_code==409 and missing.headers['cache-control']=='no-store'
        malformed=client.get(url+'not-a-digest')
        assert malformed.status_code==400
        # A newly published appended slot also refreshes a stale short catalogue.
        cache.update(catalog={'schema_version':1,'model':model,'albums':[]},time=time.time())
        assert client.get(url+sha(new)).content==new
print('BOTH_MODELS_DIGEST_PIN_STALE_CATALOGUE_AND_FAIL_CLOSED_PASS')
