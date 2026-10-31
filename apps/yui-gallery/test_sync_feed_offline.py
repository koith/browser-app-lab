#!/usr/bin/env python3
"""Offline regression for the public SNS feed refresh adapter.

No network, no real feed modification, and no authenticated sources.
"""
import json
import runpy
import sys
import tempfile
import types
from pathlib import Path

SOURCE=Path(__file__).with_name('sync_feed.py').read_text(encoding='utf-8')

def run_case(old_count,new_count,truncated=False,should_fail=False):
    with tempfile.TemporaryDirectory() as folder:
        folder=Path(folder)
        (folder/'sync_feed.py').write_text(SOURCE,encoding='utf-8')
        existing={'images':[{'url':f'https://example.test/old{i}.jpg','post':'','date':'2025-01-01'} for i in range(old_count)]}
        feed=folder/'feed.json'
        feed.write_text(json.dumps(existing),encoding='utf-8')
        old_bytes=feed.read_bytes()
        archive=types.ModuleType('sns_archive')
        archive.discover=lambda session,**kwargs:{
            'images':[{'url':f'https://example.test/new{i}.jpg','post':'https://x.com/super_yuisan/status/2115374736679309345','id':f'new{i}'} for i in range(new_count)],
            'pages':[{'url':'https://example.test/media','found':new_count,'new':new_count}],
            'truncated':truncated,
        }
        public=types.ModuleType('public_photo_archive')
        public.PublicSession=lambda delay=0.35:object()
        original_sns=sys.modules.get('sns_archive')
        original_public=sys.modules.get('public_photo_archive')
        sys.modules['sns_archive']=archive
        sys.modules['public_photo_archive']=public
        try:
            try:runpy.run_path(str(folder/'sync_feed.py'),run_name='__main__')
            except RuntimeError:
                if not should_fail:raise
                assert feed.read_bytes()==old_bytes
                return
            assert not should_fail
            result=json.loads(feed.read_text(encoding='utf-8'))
            assert len(result['images'])==old_count+new_count
            assert result['complete_pagination'] is (not truncated)
            assert all(x.get('url') for x in result['images'])
        finally:
            if original_sns is None:sys.modules.pop('sns_archive',None)
            else:sys.modules['sns_archive']=original_sns
            if original_public is None:sys.modules.pop('public_photo_archive',None)
            else:sys.modules['public_photo_archive']=original_public

run_case(70,60,truncated=False)
run_case(70,60,truncated=True)
run_case(70,0,should_fail=True)
print('YUI_FEED_ADAPTER_OFFLINE_PASS')
