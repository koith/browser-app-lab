#!/usr/bin/env python3
"""Offline reproducible all-album reverse/title selection completeness tests."""
from reverse_full_corpus_ab import full_census,partition,all_album_seeds,search_image,ROOT


def test():
    c=full_census(ROOT)
    s=c['summary']
    assert s['owner_albums_by_model']=={'yui':32,'mimmi':80},s
    assert s['missing_owner_albums_without_photo_seed']==0,s
    assert s['all_title_work_leads']==30,s
    assert s['unique_albums_with_seeds']==112,s
    assert s['all_public_reverse_photo_seeds']>=112,s
    for shards in (1,5,8,16):
        grouped=[x for model in ('yui','mimmi') for shard in range(shards)
                    for x in c['seeds'] if x['model']==model and partition(x,shards)==shard]
        titles=[x for model in ('yui','mimmi') for shard in range(shards)
                    for x in c['title_leads'] if x['model']==model and partition(x,shards)==shard]
        assert len(grouped)==len(c['seeds']),shards
        assert len(titles)==30,shards
        assert len({(x['model'],x['album_id'],x['owner_sha256']) for x in grouped})==len(grouped)
    import reverse_full_corpus_ab as m
    funcs=[m.multi_search,m.lens_query,m.tineye_query,m.yandex_site_search]
    m.multi_search=lambda session,url:{
        'engine_statuses':{'yandex':'ok','bing':'ok'},
        'links':[{'url':'https://photos.example/yui-photo','label':'심유이 새 공개 화보'}]}
    m.lens_query=lambda session,url:{'status':'captcha','links':[]}
    m.tineye_query=lambda session,url:{'status':'no_results','links':[]}
    m.yandex_site_search=lambda seed,session:{
        'search_status':{'yandex_sites':'ok'},
        'candidate_pages':[{'url':'https://photos.example/yui-photo','label':'심유이 새 공개 화보'}]}
    try:
        seed={'model':'yui','album_id':'work','album_title':'Yui','owner_sha256':'a'*64,
              'owner_photo_count':1,'seed_position':0,'public_image_url':'https://example.org/photo.jpg'}
        o=search_image(seed,None)
        assert o['candidate_source_urls']==1,o
        assert o['approved_candidate_source_urls']==1,o
        assert o['new_originals_stored']==o['new_gallery_photos']==0,o
    finally:
        m.multi_search,m.lens_query,m.tineye_query,m.yandex_site_search=funcs
    print('REVERSE_ALL_OWNER_AND_TITLE_CENSUS_OFFLINE_PASS',s)


if __name__=='__main__':test()
