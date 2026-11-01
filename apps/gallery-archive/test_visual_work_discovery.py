#!/usr/bin/env python3
"""Offline regression: user-visible titles are leads, never stored photos."""
import json
import tempfile
from pathlib import Path

from visual_work_discovery import discover, unwrap_link, same_work, search_one


class Response:
    status_code = 200
    headers = {'Content-Type': 'text/html; charset=utf-8'}
    def __init__(self, text):
        self.text = text


class FakeClient:
    def get(self, url, params=None, **kwargs):
        assert kwargs['allow_redirects'] is False
        query = params['q']
        if '639' in query:
            title = 'ArtGravia Vol.639 Yui publicly visible sample'
            target = 'https://www.example.org/gallery/artgravia-639'
        else:
            title, target = 'Unrelated site', 'https://www.example.org/other'
        if 'bing.com' in url:
            return Response('<li class="b_algo"><h2><a href="'+target+'">'+title+'</a></h2></li>')
        return Response('<div class="result"><a class="result__a" href="'+target+'">'+title+'</a></div>')


def run():
    assert unwrap_link('https://duckduckgo.com/l/?uddg=https%3A%2F%2Fexample.org%2Fphoto') == 'https://example.org/photo'
    for invalid in ('http://example.org/a', 'https://example.org/file.zip',
                    'https://bad:pw@example.org/', 'https://duckduckgo.com/html/?q=Yui'):
        assert unwrap_link(invalid) is None
    assert not same_work({'series': 'ArtGravia', 'volume': 639},
                         {'title': 'ArtGravia Vol.663 [Yui]'})
    assert not same_work({'series': 'Yui', 'work_name': 'Summer'},
                         {'title': '[MilkyBomb] Yui Vol.1 Last Summer'})
    with tempfile.TemporaryDirectory() as d:
        root = Path(d)
        base = root / 'yui-gallery'
        base.mkdir()
        (base/'owner-index.json').write_text(json.dumps({'albums': [
            {'id': 'green', 'title': 'Yui Green',
             'images': [{'sha256': 'a'*64}]},
            {'id': 'athletic', 'title': 'Yui Athletic Club',
             'images': [{'sha256': f'{n:064x}'} for n in range(1,105)]},
            {'id': 'artgravia-663', 'title': '[AI Enhanced] ArtGravia Vol.663 — Yui',
             'images': [{'sha256': f'{n:064x}'} for n in range(201,233)]}
        ]}))
        (base/'albums.json').write_text(json.dumps({'albums': [
            {'id': 'mf01', 'title': 'Yui Sim Vol.1 Baby Blue — 사진집'}
        ]}))
        plan = discover(root, Path(__file__).with_name('visual-work-leads.json'))
        works = {w['key']: w for w in plan['works']}
        for key in ('yui-green', 'artgravia-663', 'yui-baby-blue'):
            assert works[key]['catalogue_matches'], key
        for number in (639,650,670,677,684,693):
            assert not works[f'artgravia-{number}']['catalogue_matches'], number
        assert not works['yui-summer']['catalogue_matches']
        assert works['yui-green']['classification'] == 'mapped_low_photo_count_priority_search'
        assert works['yui-green']['owner_original_distinct_photos'] == 1
        assert works['artgravia-663']['classification'] == 'mapped_without_verified_originals_priority_search'
        assert works['artgravia-663']['owner_original_distinct_photos'] == 0
        assert works['yui-athletic-club']['classification'] == 'mapped_reference_count_met_completeness_unverified'
        assert not works['yui-athletic-club']['priority_search_required']
        assert plan['mapped_low_coverage_works'] >= 2
        assert plan['unmapped_works'] == sum(not x['catalogue_matches'] for x in works.values())
        assert plan['unmapped_works'] >= 14, plan['unmapped_works']
        scan = discover(root, Path(__file__).with_name('visual-work-leads.json'),
                        search=True, max_works=1, client=FakeClient())
        c = scan['works'][0]['search_result']['candidate_pages']
        assert c and all(x['status'] == 'unverified_search_lead_not_downloaded' for x in c)
        assert scan['physical_new_files'] == scan['visible_new_files'] == 0
    print('VISUAL_WORK_DISCOVERY_OFFLINE_PASS')


if __name__ == '__main__':
    run()
