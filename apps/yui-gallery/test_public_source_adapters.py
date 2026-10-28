"""Cross-model exclusions, full displayed links and subset registration regression."""
import hashlib
import io
import json
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import Mock
from pathlib import Path

from PIL import Image

from build_additional_source_manifest import build
from collect_public_sources import (djawa_model_index, djawa_samples, gamersky_article, hacosta_model_photo, imgcup_teddy,
                                    inven_article, photographer_portfolio, crazygiant_samples, sportsseoul_daum_article,
                                    ajunews_may_cover, imgcup_model_index, imgcup_work, collect)


class SourceAdapterTests(unittest.TestCase):
    def test_imgcup_pagination_dispatches_articles_to_the_work_adapter(self):
        index='https://www.imgcup.com/keyword/yui-%EC%9C%A0%EC%9D%B4'
        pages={index:'''<h2 class="entry-title"><a href="/wet1.html">Yui 유이 Wet Set.01</a></h2>
               <div class="penci-pagination"><a href="'''+index+'''/page/2">2</a></div>''',
               index+'/page/2':'<h2 class="entry-title"><a href="/wet2.html">Yui 유이 Wet Set.02</a></h2>'}
        for number in (1,2):
            pages[f'https://www.imgcup.com/wet{number}.html']=f'''<h1>Yui 유이 Wet Set.0{number}</h1>
            <div class="entry-content"><img src="https://cdn.imgcup.com/wet{number}.jpg"></div>'''
        client=Mock();client.get.side_effect=lambda url:SimpleNamespace(content=pages[url].encode(),url=url)
        with tempfile.TemporaryDirectory() as temporary:
            result=collect([{'url':index,'adapter':'imgcup-yui-index','max_pages':4}],temporary,
                           download=False,client=client)
        self.assertEqual(len(result['works']),2)
        self.assertEqual(len(result['public_photo_candidates']),2)
        self.assertEqual([p['adapter'] for p in result['pages']],
                         ['imgcup-yui-index','imgcup-work','imgcup-yui-index','imgcup-work'])

    def test_imgcup_model_discovery_keeps_credited_cards_and_observed_index_pages(self):
        body = '''<h2 class="entry-title"><a href="/wet.html">Yui 유이, Wet ゆい Set.02</a></h2>
        <h2 class="entry-title"><a href="/other.html">Other model</a></h2>
        <h2 class="entry-title"><a href="/video.html">Yui 유이 Vol.3 Videos EP1</a></h2>
        <nav class="nav-links"><a href="/keyword/yui-%EC%9C%A0%EC%9D%B4/page/2">2</a>
        <a href="/keyword/other/page/2">Other</a><a href="https://outside.test/page/2">Offsite</a></nav>
        <aside><a href="/unreviewed.html">Yui 유이</a></aside>'''
        _, _, nexts = imgcup_model_index(body, 'https://www.imgcup.com/keyword/yui-%EC%9C%A0%EC%9D%B4')
        self.assertEqual(nexts, ['https://www.imgcup.com/wet.html',
                                'https://www.imgcup.com/keyword/yui-%EC%9C%A0%EC%9D%B4/page/2'])
        with self.assertRaises(ValueError):
            imgcup_model_index(body, 'https://www.imgcup.com/keyword/other')

    def test_imgcup_work_does_not_guess_book_identity_or_count_from_article_links(self):
        body = '''<h1>Yui 유이, Yo-U Vol.03 Photobook Set.01</h1>
        <div class="entry-content"><a href="https://cdn.imgcup.com/full.jpg?v=1">
        <img src="https://cdn.imgcup.com/thumb.jpg"></a>
        <img srcset="https://cdn.imgcup.com/small.webp 400w, https://cdn.imgcup.com/large.webp 1200w">
        <img src="https://cdn.imgcup.com/advert.gif"><img src="https://outside.test/other.jpg"></div>
        <aside><img src="https://cdn.imgcup.com/related.jpg"></aside>'''
        works, photos, nexts = imgcup_work(body, 'https://www.imgcup.com/work.html')
        self.assertEqual([p['url'] for p in photos], ['https://cdn.imgcup.com/full.jpg?v=1',
                                                     'https://cdn.imgcup.com/large.webp'])
        self.assertIsNone(works[0]['candidate_work_id'])
        self.assertFalse(works[0]['full_edition_acquired'])
        self.assertEqual(nexts, [])
        works, _, _ = imgcup_work(body.replace('Yo-U Vol.03', 'SWEETBOX Vol.39'),
                                 'https://www.imgcup.com/work.html')
        self.assertEqual(works[0]['candidate_work_id'], 'ramen125')
        for changed in (body.replace('Yui 유이', 'Other'), body.replace('Photobook', 'Videos EP1')):
            with self.assertRaises(ValueError):
                imgcup_work(changed, 'https://www.imgcup.com/work.html')
        with self.assertRaisesRegex(ValueError, 'AI editions'):
            imgcup_work(body.replace('Photobook', 'AI Enhanced Photobook'), 'https://www.imgcup.com/work.html')

    def test_player_named_samples_exclude_uncredited_generic_product_cover(self):
        stem = 'https://cdn.imweb.me/upload/S202010013208049566f15/'
        body = f'''<title>THE PLAYER ISSUE 5 [심혜성] : 크레이지자이언트</title>
        <div class="board_txt_area">ISSUE 5 [심혜성]<img src="{stem}sample.jpg">
        <img src="{stem}5bb2d6488f51d.png"></div>'''
        works, photos, _ = crazygiant_samples(body, 'https://crazygiant.imweb.me/giantgirl/')
        self.assertEqual([r['url'] for r in photos], [stem+'sample.jpg'])
        self.assertEqual(works[0]['title'], 'THE PLAYER ISSUE 5 — 심혜성')
        self.assertFalse(works[0]['full_edition_acquired'])

    def test_cover_article_excludes_related_images_and_other_subject(self):
        url = 'https://image.ajunews.com/content/image/2023/04/26/cover.jpg'
        body = f'''<h1>모델 유이, 크레이지 자이언트 5월 호 표지</h1>
        <div id="articleBody"><div class="imgBox"><img src="{url}"></div></div>
        <aside class="imgBox"><img src="{url.replace('cover', 'other')}"></aside>'''
        _, photos, _ = ajunews_may_cover(body, 'https://www5.ajunews.com/view/1')
        self.assertEqual([r['url'] for r in photos], [url])
        with self.assertRaises(ValueError):
            ajunews_may_cover(body.replace('모델 유이', '다른 모델'), 'https://www5.ajunews.com/view/1')

    def test_crazygiant_requires_issue_credit_and_excludes_related_work(self):
        url = 'https://cdn.imweb.me/upload/S202010013208049566f15/photo.png'
        body = f'''<title>5월 사랑스러운 아내 _ 유이 : 크레이지자이언트</title>
        <div class="board_txt_area">크레이지 자이언트 23년 5월호<img src="{url}"></div>
        <aside><img src="https://cdn.imweb.me/upload/S202010013208049566f15/other.png"></aside>'''
        works, photos, _ = crazygiant_samples(body, 'https://crazygiant.imweb.me/giantgirl/')
        self.assertEqual([r['url'] for r in photos], [url])
        self.assertFalse(works[0]['full_edition_acquired'])
        for changed in (body.replace('_ 유이', '_ 다른모델'), body.replace('23년 5월호', '24년 5월호')):
            with self.assertRaises(ValueError):
                crazygiant_samples(changed, 'https://crazygiant.imweb.me/giantgirl/')

    def test_news_uses_explicit_original_and_individual_caption_only(self):
        url = 'https://t1.daumcdn.net/news/202003/26/SPORTSSEOUL/original.jpg'
        body = f'''<article><h3 class="tit_view">심혜성 촬영 기사</h3>
        <div class="article_view"><img alt="심혜성. 이주상기자" data-org-src="{url}"
        src="https://img1.daumcdn.net/thumb/R658x0.q70/?fname={url}">
        <img alt="다른 모델" data-org-src="{url.replace('original', 'other')}"></div></article>
        <aside><img alt="심혜성" data-org-src="{url.replace('original', 'related')}"></aside>'''
        _, photos, _ = sportsseoul_daum_article(body, 'https://v.daum.net/v/1')
        self.assertEqual([r['url'] for r in photos], [url])
        with self.assertRaises(ValueError):
            sportsseoul_daum_article(body.replace('심혜성 촬영 기사', '다른 모델'), 'https://v.daum.net/v/1')

    def test_imgcup_teddy_requires_the_named_work_and_article_full_links(self):
        body = '''<h1 class="entry-title">SWEETBOX Yui 유이 – Teddy Bear Part01</h1>
        <div class="entry-content"><a href="https://cdn.imgcup.com/2026/Teddy-Bear-full.jpg">
        <img src="https://cdn.imgcup.com/2026/Teddy-Bear-small.jpg"></a>
        <img src="https://cdn.imgcup.com/advert.jpg"></div>
        <aside><img src="https://cdn.imgcup.com/Teddy-Bear-related.jpg"></aside>'''
        _, photos, _ = imgcup_teddy(body, 'https://www.imgcup.com/teddy.html')
        self.assertEqual([p['url'] for p in photos], ['https://cdn.imgcup.com/2026/Teddy-Bear-full.jpg'])
        self.assertEqual(photos[0]['work_id'], 'teddy-bear97')
        with self.assertRaises(ValueError):
            imgcup_teddy(body.replace('Yui 유이', 'Other'), 'https://www.imgcup.com/teddy.html')

    def test_publisher_model_index_follows_only_its_work_grid(self):
        body = '''<title>Yui – Djawa Photo</title><section class="grid-item">
        <a href="/portfolio/work/">Work</a></section>
        <nav><a href="/portfolio/unrelated/">Other model</a></nav>'''
        _, _, nexts = djawa_model_index(body, 'https://djawaphoto.com/yui')
        self.assertEqual(nexts, ['https://djawaphoto.com/portfolio/work/'])

    def test_djawa_excludes_covers_video_and_related_thumbnails(self):
        body = '''<title>Sharp Lesson – Djawa Photo</title><p>Djawa × Yui
        total 190 extremely-high resolution (8640 × 5760) photos</p>
        <div class="lightbox-photoswipe">
        <img class="grid-item-img" alt="sample_01" data-src="https://djawaphoto.com/a-small.jpg"
          data-srcset="https://djawaphoto.com/a-small.jpg 300w, https://djawaphoto.com/a.jpg 1200w">
        <img class="grid-item-img" alt="sample_cv1" data-src="https://djawaphoto.com/cover.jpg">
        <img class="grid-item-img" alt="sample_video_thumbnail" data-src="https://djawaphoto.com/video.jpg">
        </div><img alt="sample_02" data-src="https://djawaphoto.com/related.jpg">'''
        works, photos, _ = djawa_samples(body, 'https://djawaphoto.com/work/')
        self.assertEqual([p['url'] for p in photos], ['https://djawaphoto.com/a.jpg'])
        self.assertEqual(works[0]['advertised_photos'], 190)
        self.assertFalse(works[0]['full_edition_acquired'])

    def test_event_selects_only_adjacent_explicitly_credited_exhibitor(self):
        body = '''<img src="https://blog.hacosta.co.jp/before.jpg">
        <p><span><a href="https://x.com/super_yuisan">シム・ゆい</a></span><br>
        <img src="https://blog.hacosta.co.jp/correct.jpg"></p>
        <p><a href="https://x.com/other">Other</a><img src="https://blog.hacosta.co.jp/other.jpg"></p>'''
        _, photos, _ = hacosta_model_photo(body, 'https://blog.hacosta.co.jp/report/')
        self.assertEqual([p['url'] for p in photos], ['https://blog.hacosta.co.jp/correct.jpg'])

    def test_article_body_full_links_and_same_article_pagination(self):
        body = '''<div class="Mid2L_con"><p class="GsImageLabel"><a
        href="https://www.gamersky.com/showimage/id_gamersky.shtml?https://img1.gamersky.com/full.jpg">
        <img src="https://img1.gamersky.com/full_S.jpg"></a></p></div>
        <img src="https://img1.gamersky.com/advert.jpg"><div class="page_css">
        <a href="/news/202512/2066711_2.shtml">2</a><a href="/news/202512/other.shtml">Related</a></div>'''
        _, photos, nexts = gamersky_article(body, 'https://www.gamersky.com/news/202512/2066711.shtml')
        self.assertEqual([p['url'] for p in photos], ['https://img1.gamersky.com/full.jpg'])
        self.assertEqual(nexts, ['https://www.gamersky.com/news/202512/2066711_2.shtml'])

    def test_board_body_excludes_comments_and_preserves_observed_resize_url(self):
        body = '''<title>심유이 인스타</title><div id="powerbbsContent">
        <img src="https://upload3.inven.co.kr/photo.jpg?MW=800"></div>
        <div class="comments"><img src="https://upload3.inven.co.kr/comment.jpg"></div>'''
        _, photos, _ = inven_article(body, 'https://www.inven.co.kr/board/1')
        self.assertEqual([p['url'] for p in photos], ['https://upload3.inven.co.kr/photo.jpg?MW=800'])
        with self.assertRaisesRegex(ValueError, 'does not credit'):
            inven_article(body.replace('심유이', 'Other'), 'https://www.inven.co.kr/board/1')

    def test_portfolio_requires_exact_subject_and_original_post(self):
        post = {'tweetId':'1','cosplayer':'@super_yuisan','author':'@super_yuisan',
                'originalUrl':'https://x.com/super_yuisan/status/1',
                'photos':[{'original':'https://pbs.twimg.com/media/full.jpg:orig'}]}
        other = {**post, 'cosplayer':'@other', 'photos':[{'original':'https://pbs.twimg.com/media/other.jpg:orig'}]}
        _, photos, _ = photographer_portfolio('const data='+json.dumps([post, other]), 'https://example.com/app.js')
        self.assertEqual(len(photos), 1)
        self.assertEqual(photos[0]['photographer_credit'], '@photo_vicc')

    def test_new_timeline_rows_append_without_replacing_previous_pose(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            folder = root/'collection';folder.mkdir()
            def photo(number, color, stem):
                stream=io.BytesIO();Image.new('RGB',(300,400),color).save(stream,format='PNG')
                raw=stream.getvalue();path=folder/(stem+'.png');path.write_bytes(raw)
                return {'number':number,'url':'https://pbs.twimg.com/media/'+stem+'.png?name=orig',
                        'sha256':hashlib.sha256(raw).hexdigest(),'bytes':len(raw),'width':300,
                        'height':400,'file':path.name,'origin_page':'https://x.com/super_yuisan/status/1'}
            old = photo(1, 'red', 'old')
            new = photo(1, 'blue', 'new')
            def incoming(rows):
                (folder/'manifest.json').write_text(json.dumps({'id':'public-test','title':'Public subset',
                'expected':len(rows),'images':rows,'not_complete_photobook':True,
                'expected_total_unknown':True,'collection_kind':'creator_public_photographs'}))
            out=root/'out.json';incoming([old]);build([folder],out)
            incoming([new,{**old,'number':2}]);build([folder],out)
            album=json.loads(out.read_text())['albums'][0]
            self.assertEqual([p['sha256'] for p in album['images']], [old['sha256'],new['sha256']])
            self.assertEqual([p['number'] for p in album['images']], [1,2])
            self.assertFalse(album['complete_sequence'])
            self.assertIsNone(album['missing_numbers'])


if __name__ == '__main__':
    unittest.main()
