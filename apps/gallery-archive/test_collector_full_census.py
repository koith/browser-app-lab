#!/usr/bin/env python3
"""Fail closed when the exhaustive comparison silently drops a registered work."""
from collector_full_census import census,shard_key,select,ROOT


def test_census():
    d=census(ROOT);s=d['summary'];targets=d['targets']
    assert s['owner']['yui']['registered_albums']==32,s
    assert s['owner']['mimmi']['registered_albums']==80,s
    assert s['source_page_urls_recorded']>=938,s
    assert s['all_targets_by_kind']['catalogue']==20,s
    assert s['all_targets_by_kind']['visual_lead']==30,s
    assert s['all_targets_by_kind']['social']>=4,s
    assert s['total_targets']>150,s
    assert len(targets)==s['total_targets']
    assert any(t['model']=='yui' and t['kind']=='work' and
               t['id']=='cream228' and len(t['urls'])>=450 for t in targets)
    assert any(t['model']=='mimmi' and t['kind']=='work' and
               t['id']=='djawa-my-summer-vacation-vol-5' for t in targets)
    assert any(t['model']=='yui' and t['kind']=='visual_lead' and not t['urls'] for t in targets)
    assert any(t['kind']=='catalogue' and t['id']=='mimmi-djawa-official' for t in targets)
    assert any(t['kind']=='social' and t['model']=='mimmi' for t in targets)
    for shards in (1,5,8,16):
        parts=[select(d,model,n,shards)
               for model in ('yui','mimmi') for n in range(shards)]
        keys=[(a['model'],a['kind'],a['id']) for part in parts for a in part]
        assert len(keys)==len(set(keys))==len(targets),(shards,len(keys),len(targets))
    # Work identity may be an alias, but no work is erased or merged without evidence.
    assert all(not t.get('complete',False) for t in targets)
    print('FULL_GALLERY_CENSUS_OFFLINE_PASS',s)


if __name__=='__main__':test_census()
