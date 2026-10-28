#!/usr/bin/env python3
"""Collect creator-published public post attachments into individual original files.

Only explicit post attachments and visible same-profile pagination are followed.
Quoted posts, avatars, video stills and unrelated retweets are excluded.
"""
from __future__ import annotations

import argparse
import json
import re
import time
from pathlib import Path
from urllib.parse import parse_qs, urljoin, urlsplit

from bs4 import BeautifulSoup

from public_photo_archive import PublicSession, atomic_json, download_individuals, utcnow

ROOT = 'https://teapawt.net/super_yuisan/media'
PROFILE = 'super_yuisan'
MEDIA = re.compile(r'^https://pbs\.twimg\.com/media/[A-Za-z0-9_-]+\.(?:jpg|jpeg|png|webp)(?:\?[^\s]*)?$', re.I)
STATUS = re.compile(r'^/([A-Za-z0-9_]+)/status/(\d+)(?:#m)?$')


def record_page(html, url, profile=PROFILE):
    soup = BeautifulSoup(html, 'html.parser')
    photos = {}
    for post in soup.select('.timeline-item[data-username]'):
        author = post.get('data-username', '')
        if author.casefold() != profile.casefold():
            continue
        link = post.select_one('a.tweet-link[href]')
        match = STATUS.fullmatch(link['href']) if link else None
        if not match or match[1].casefold() != profile.casefold():
            continue
        caption = post.select_one('.tweet-content')
        work_links = [a['href'] for a in caption.select('a[href]')
                      if any((urlsplit(a['href']).hostname or '') == domain or (urlsplit(a['href']).hostname or '').endswith('.'+domain) for domain in
                             ['ctee.kr','djawaphoto.com','moviefantasy.co.kr','gumroad.com','linktoma.to'])] if caption else []
        caption = caption.get_text(' ', strip=True) if caption else ''
        date = post.select_one('.tweet-date a[title]')
        # A quoted image may belong to a different person even inside this author's post.
        for image in post.select('.attachments a.still-image[href]'):
            if image.find_parent(class_='timeline-item') is not post:
                continue
            if any('quote' in c for parent in image.parents if parent is not post
                   for c in parent.get('class', [])):
                continue
            image_url = image['href']
            if not MEDIA.fullmatch(image_url):
                continue
            # Prefer only the site's explicit original-size attachment link.
            if parse_qs(urlsplit(image_url).query).get('name') != ['orig']:
                continue
            photo_id = urlsplit(image_url).path.rsplit('/', 1)[-1].split('.')[0]
            photos[image_url] = {
                'id': photo_id, 'url': image_url,
                'origin_page': 'https://x.com/' + profile + '/status/' + match[2],
                'post': 'https://x.com/' + profile + '/status/' + match[2],
                'author': profile, 'caption': caption,
                'public_work_links': list(dict.fromkeys(work_links)),
                'published_at_text': date['title'] if date else None,
                'discovery_page': url, 'source_attribute': 'public_post_original_attachment',
            }
    next_urls = []
    parsed = urlsplit(url)
    for link in soup.select('.show-more a[href], a.more[href]'):
        candidate = urljoin(url, link['href'])
        target = urlsplit(candidate)
        if (target.scheme == 'https' and target.netloc == parsed.netloc
                and target.path == '/' + profile + '/media'
                and parse_qs(target.query).get('cursor')):
            next_urls.append(candidate)
    # Current frontend wraps its Load more link in a show-more div; the fallback
    # still requires an explicit same-profile media cursor visible in an anchor.
    if not next_urls:
        for link in soup.select('a[href]'):
            candidate = urljoin(url, link['href'])
            target = urlsplit(candidate)
            if (target.scheme == 'https' and target.netloc == parsed.netloc
                    and target.path == '/' + profile + '/media'
                    and parse_qs(target.query).get('cursor')):
                next_urls.append(candidate)
    return list(photos.values()), list(dict.fromkeys(next_urls))


def discover(client, max_pages=85, delay=1.0, root=ROOT):
    url, visited, records, pages = root, set(), {}, []
    empty_streak = 0
    while url and len(pages) < max_pages and url not in visited:
        visited.add(url)
        try:
            response = client.get(url)
            photos, next_urls = record_page(response.text, url)
            new = 0
            for row in photos:
                if row['url'] not in records:
                    records[row['url']] = row
                    new += 1
            next_url = next((u for u in next_urls if u not in visited), None)
            pages.append({'url': url, 'found': len(photos), 'new': new,
                          'response_sha256': __import__('hashlib').sha256(response.content).hexdigest(),
                          'next_url': next_url})
            print('PUBLIC_POST_PAGE', len(pages), 'new', new, 'total', len(records), flush=True)
            url = next_url
            empty_streak = empty_streak + 1 if not new else 0
            # A page of videos/filtered posts does not imply the end of photos.
            # Some frontends emit an endless changing empty cursor at the end.
            if empty_streak >= 7:
                break
            time.sleep(delay)
        except Exception as error:
            pages.append({'url': url, 'error': str(error)[:350]})
            break
    return {'generated_at': utcnow(), 'source': root, 'pages': pages,
            'images': list(records.values()), 'truncated': bool(url),
            'stopped_on_empty_cursor_limit': empty_streak >= 7,
            'not_complete_photobook': True, 'public_creator_posts_only': True}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--max-pages', type=int, default=85)
    parser.add_argument('--delay', type=float, default=1.0)
    parser.add_argument('--output', type=Path, default=Path('yui-sns-individuals'))
    parser.add_argument('--discovery', type=Path)
    parser.add_argument('--discover-only', action='store_true')
    parser.add_argument('--max-images', type=int)
    args = parser.parse_args()
    client = PublicSession(delay=max(args.delay, 0.2))
    if args.discovery:
        discovery = json.loads(args.discovery.read_text())
    else:
        discovery = discover(client, max_pages=args.max_pages, delay=args.delay)
    args.output.mkdir(parents=True, exist_ok=True)
    atomic_json(args.output / 'discovery.json', discovery)
    if args.discover_only:
        print('PUBLIC_POST_DISCOVERY', len(discovery['images']), 'pages', len(discovery['pages']), flush=True)
        return
    records = discovery['images']
    if args.max_images is not None:
        records = records[:args.max_images]
    report = download_individuals(records, args.output, client)
    print('PUBLIC_POST_FINAL', json.dumps({key: report[key] for key in
          ('unique_files', 'new_unique_files_this_run', 'skipped_existing_urls')}),
          'failures', len(report['failures']), flush=True)
    if report['failures'] or not report['images']:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
