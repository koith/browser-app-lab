#!/usr/bin/env python3
"""Publisher catalogue and narrowly scoped public article/photo adapters.

These adapters follow displayed links only. Catalogue records and downloaded
photographs are separate outputs; samples never count as a complete paid book.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path
from urllib.parse import parse_qs, urljoin, urlsplit

from bs4 import BeautifulSoup

from public_photo_archive import PublicSession, atomic_json, download_individuals, utcnow


def soup_for(raw):
    # Bytes preserve the declared HTML encoding instead of requests' Latin-1 default.
    return BeautifulSoup(raw, 'html.parser')


def image_record(url, page, kind, country, **extra):
    return {'url': url, 'origin_page': page, 'discovery_page': page,
            'source_attribute': 'explicit_public_full_image_link',
            'collection_kind': kind, 'source_country': country, **extra}


def largest_displayed_image(image, page):
    candidates = []
    for attribute in ('srcset', 'data-srcset'):
        for item in image.get(attribute, '').split(','):
            match = re.fullmatch(r'\s*(https://\S+)\s+(\d+)w\s*', item)
            if match:
                candidates.append((int(match[2]), match[1]))
    for attribute in ('data-full-url', 'data-src', 'src'):
        value = image.get(attribute, '')
        if value.startswith('https://'):
            candidates.append((int(image.get('width', 0) or 0), value))
    anchor = image.find_parent('a', href=True)
    if anchor:
        linked = urljoin(page, anchor['href'])
        if re.search(r'\.(?:jpg|jpeg|webp|png)(?:\?|$)', linked, re.I):
            return linked
    return max(candidates, default=(0, None), key=lambda x: x[0])[1]


def djawa_model_index(raw, page):
    soup = soup_for(raw)
    if not soup.title or not soup.title.get_text().startswith('Yui – Djawa Photo'):
        raise ValueError('Not the publisher Yui model catalogue')
    links = [urljoin(page, a['href']) for a in soup.select('section.grid-item a[href]')
             if urlsplit(urljoin(page, a['href'])).hostname == 'djawaphoto.com'
             and urlsplit(urljoin(page, a['href'])).path.startswith('/portfolio/')]
    return [], [], list(dict.fromkeys(links))


def djawa_samples(raw, page):
    soup = soup_for(raw)
    content = soup.get_text(' ', strip=True)
    if 'Djawa × Yui' not in content:
        raise ValueError('Publisher page does not explicitly credit Yui')
    records = []
    for image in soup.select('.lightbox-photoswipe img.grid-item-img[data-src]'):
        # Cover layouts and video thumbnails are not photographs in the set.
        if not re.fullmatch(r'sample_\d+', image.get('alt', '')):
            continue
        url = largest_displayed_image(image, page)
        if url and urlsplit(url).hostname == 'djawaphoto.com':
            records.append(image_record(url, page, 'official_public_samples', 'KR',
                                        publisher='DJAWA', sample_label=image['alt']))
    count = re.search(r'total\s+(\d+)\s+extremely', content)
    dimensions = re.search(r'(\d{4,5})\s*×\s*(\d{4,5})', content)
    work = {'publisher': 'DJAWA', 'source_country': 'KR', 'official_source': True,
            'title': soup.select_one('title').get_text().split(' – Djawa Photo')[0],
            'url': page, 'kind': 'photobook',
            'advertised_photos': int(count[1]) if count else None,
            'advertised_dimensions': [int(dimensions[1]), int(dimensions[2])] if dimensions else None,
            'visible_photo_samples': len(records), 'full_edition_acquired': False,
            'access_status': 'public_samples_only_purchase_required_for_full_edition'}
    return [work], records, []


def hacosta_model_photo(raw, page):
    soup = soup_for(raw)
    profile = soup.find('a', href='https://x.com/super_yuisan')
    if not profile:
        raise ValueError('No explicit model profile in the article')
    # The named paragraph's immediately following photograph belongs to this
    # exhibitor. Never collect the article's dozens of unrelated cosplayers.
    image = None
    for element in profile.next_elements:
        if getattr(element, 'name', None) == 'a' and element.get('href', '').startswith('https://x.com/'):
            break
        if getattr(element, 'name', None) == 'img':
            image = element
            break
    if image is None:
        raise ValueError('Named exhibitor photo was not found adjacent to the credit')
    url = largest_displayed_image(image, page)
    if urlsplit(url).hostname != 'blog.hacosta.co.jp':
        raise ValueError('Unexpected event photo host')
    return [], [image_record(url, page, 'official_event_report', 'JP', publisher='Hacosta / acosta!',
                              subject_evidence='adjacent explicit @super_yuisan credit',
                              photographer_credit='かぷ / @camepuchi (article section credit)')], []


def gamersky_article(raw, page):
    soup = soup_for(raw)
    article = soup.select_one('.Mid2L_con')
    if not article:
        raise ValueError('Missing article body')
    records = []
    for image in article.select('p.GsImageLabel img'):
        anchor = image.find_parent('a', href=True)
        link = anchor['href'] if anchor else ''
        # The page explicitly supplies the full photograph inside its viewer URL.
        match = re.search(r'\?(https://img\d\.gamersky\.com/[^\s]+)', link)
        if match:
            records.append(image_record(match[1], page, 'public_editorial_photos', 'CN', publisher='GamerSky'))
    path = urlsplit(page).path
    stem = re.sub(r'(?:_\d+)?\.shtml$', '', path)
    nexts = []
    for anchor in soup.select('.page_css a[href]'):
        url = urljoin(page, anchor['href'])
        target = urlsplit(url)
        if target.hostname == 'www.gamersky.com' and re.fullmatch(re.escape(stem) + r'(?:_\d+)?\.shtml', target.path):
            nexts.append(url)
    return [], records, list(dict.fromkeys(nexts))


def inven_article(raw, page):
    soup = soup_for(raw)
    if not soup.title or '심유이' not in soup.title.get_text():
        raise ValueError('Board article title does not credit the requested model')
    article = soup.select_one('#powerbbsContent')
    if not article:
        raise ValueError('Missing board article body')
    records = []
    for image in article.select('img[src]'):
        url = largest_displayed_image(image, page)
        if url and re.fullmatch(r'upload\d\.inven\.co\.kr', urlsplit(url).hostname or ''):
            # Keep the observed URL. Do not invent an original by deleting MW.
            records.append(image_record(url, page, 'public_board_post', 'KR', publisher='인벤'))
    return [], records, []


def photographer_portfolio(raw, page):
    text = raw.decode('utf-8') if isinstance(raw, bytes) else raw
    decoder = json.JSONDecoder()
    records = []
    # Public frontend data is JSON embedded inside a JS assignment. Decode only
    # an exact object beginning with tweetId; do not evaluate JavaScript.
    for match in re.finditer(r'\{"tweetId":', text):
        try:
            post, _ = decoder.raw_decode(text[match.start():])
        except ValueError:
            continue
        if post.get('cosplayer') != '@super_yuisan' or post.get('author') != '@super_yuisan':
            continue
        origin = post.get('originalUrl', '')
        if not re.fullmatch(r'https://x\.com/super_yuisan/status/\d+', origin):
            continue
        for photo in post.get('photos', []):
            url = photo.get('original', '')
            if url.startswith('https://pbs.twimg.com/media/') or urlsplit(url).hostname == 'pub-376e2756f81341f087a414464f9a25ec.r2.dev':
                records.append(image_record(url, origin, 'public_photographer_portfolio', 'KR',
                                             publisher='photo_vicc', discovery_page=page,
                                             caption=post.get('tweetText', ''),
                                             photographer_credit='@photo_vicc',
                                             published_at=post.get('date')))
    return [], list({r['url']: r for r in records}.values()), []


def bcut_catalogue(raw, page):
    soup = soup_for(raw)
    grid = soup.select_one('#grid[data-model="심유이"]')
    if not grid:
        raise ValueError('Missing explicitly named model catalogue')
    works = []
    for card in grid.select('a.card[href]'):
        title = card.select_one('.mt').get_text(' ', strip=True)
        sku = parse_qs(urlsplit(card['href']).query).get('w', [None])[0]
        works.append({'publisher': 'BCUT', 'source_country': 'KR', 'official_source': False,
                      'catalogue_reference': page, 'title': title, 'sku': sku, 'url': card['href'],
                      'kind': 'photo_and_video' if re.search(r'PHOTO\s*\+\s*VIDEO', title, re.I)
                      else 'video' if 'VIDEO' in title.upper() else 'photobook',
                      'published_at': card.select_one('.mp').get_text(' ', strip=True),
                      'full_edition_acquired': False,
                      'access_status': 'catalogue_only_official_age_and_purchase_access_not_bypassed'})
    return works, [], []


def publisher_title(raw, page, publisher):
    soup = soup_for(raw)
    title = soup.title.get_text(' ', strip=True) if soup.title else ''
    if not any(alias.casefold() in title.casefold() for alias in ('심유이', 'Yui Sim')):
        if soup.select_one('.permission_require_login'):
            raise PermissionError('Publisher login gate; no authentication bypass attempted')
        raise ValueError('Publisher metadata does not name this model')
    if '/place/' in page or page.endswith('/yuisim'):
        return [], [], []
    return [{'publisher': publisher, 'source_country': 'KR', 'official_source': True,
             'title': title.split(' | ')[0].split(' : MOVIE FANTASY')[0], 'url': page,
             'kind': 'video' if '[VID]' in title else 'photobook',
             'full_edition_acquired': False, 'access_status': 'public_title_only_no_full_file_access'}], [], []


ADAPTERS = {'djawa-index': djawa_model_index, 'djawa': djawa_samples, 'hacosta': hacosta_model_photo, 'gamersky': gamersky_article,
            'inven': inven_article, 'photographer': photographer_portfolio, 'bcut': bcut_catalogue}


def collect(targets, output, download=True, client=None):
    output = Path(output)
    client = client or PublicSession(delay=0.7)
    works, photos, pages = {}, {}, []
    for target in targets:
        queue, seen = [(target['url'], target['adapter'])], set()
        while queue and len(seen) < target.get('max_pages', 1):
            url, adapter_name = queue.pop(0)
            if url in seen:
                continue
            seen.add(url)
            try:
                response = client.get(url)
                snapshot = hashlib.sha256(url.encode()).hexdigest()[:16] + '.html'
                (output / 'pages').mkdir(parents=True, exist_ok=True)
                (output / 'pages' / snapshot).write_bytes(response.content)
                adapter = ADAPTERS.get(adapter_name)
                found, images, nexts = (adapter(response.content, url) if adapter else
                                        publisher_title(response.content, url, target['publisher']))
                for work in found:
                    works[work['url']] = work
                for image in images:
                    photos[image['url']] = image
                child_adapter = 'djawa' if adapter_name == 'djawa-index' else adapter_name
                queue.extend((u, child_adapter) for u in nexts if u not in seen and (u, child_adapter) not in queue)
                pages.append({'url': url, 'adapter': adapter_name, 'works': len(found),
                              'photos': len(images), 'response_sha256': hashlib.sha256(response.content).hexdigest(),
                              'snapshot': snapshot})
            except Exception as error:
                pages.append({'url': url, 'adapter': target['adapter'], 'error': str(error)[:350]})
            print('PUBLIC_SOURCE_PAGE', url, pages[-1].get('works', 0),
                  pages[-1].get('photos', 0), pages[-1].get('error', ''), flush=True)
    catalogue = {'generated_at': utcnow(), 'model': '심유이 / Yui Sim / @super_yuisan',
                 'not_exhaustive': True, 'records_are_skus_not_unique_works': True,
                 'works': list(works.values()), 'pages': pages,
                 'public_photo_candidates': list(photos.values())}
    atomic_json(output / 'catalogue.json', catalogue)
    if download:
        download_individuals(list(photos.values()), output, client, 'public_publisher_event_editorial_sources')
    return catalogue


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--targets', type=Path, default=Path(__file__).with_name('publisher-source-targets.json'))
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--catalogue-only', action='store_true')
    args = parser.parse_args()
    collect(json.loads(args.targets.read_text())['sources'], args.output, not args.catalogue_only)
