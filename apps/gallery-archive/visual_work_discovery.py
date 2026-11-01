#!/usr/bin/env python3
"""Title-first public work discovery for unregistered Yui albums.

The reverse-image sweep only visits albums already indexed. This worker starts
from independent visible work names instead. Search hits stay RESEARCH ONLY:
they are not downloaded, privately stored, or shown in the gallery.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import re
from urllib.parse import parse_qs, urlsplit, urlunsplit

import requests
from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parents[1]
LEADS = Path(__file__).with_name('visual-work-leads.json')
ENGINES = {
    'bing': ('https://www.bing.com/search', 'q'),
    'duckduckgo': ('https://html.duckduckgo.com/html/', 'q'),
}
SEARCH_HOSTS = {'bing.com', 'www.bing.com', 'duckduckgo.com',
                'www.duckduckgo.com', 'html.duckduckgo.com'}
UA = 'PersonalPublicPhotoSourceResearch/1.0'
MODEL_RE = re.compile(r'(?<![a-z])yui(?![a-z])|유이|심혜성|沈惠星|优衣|ゆい', re.I)


def compact(value):
    return re.sub(r'[^a-z0-9가-힣]+', ' ', str(value).casefold()).strip()


def source_works(root=ROOT, model='yui'):
    base = Path(root) / (model + '-gallery')
    result = []
    for file in ('owner-index.json', 'albums.json'):
        data = json.loads((base / file).read_text(encoding='utf-8'))
        for row in data.get('albums', []):
            result.append({'file': file, 'id': row.get('id'),
                           'title': row.get('title', '')})
    return result


def same_work(lead, existing):
    title = compact(existing['title'])
    series = compact(lead['series'])
    if series == 'artgravia':
        # Neighboring volume numbers must never be folded into one work.
        return 'artgravia' in title and bool(re.search(
            r'(?<!\d)' + str(lead['volume']) + r'(?!\d)', title))
    name = compact(lead.get('work_name', ''))
    if not name:
        return False
    if series == 'yui' and name == 'summer':
        # "Yui Summer" is not "Yui Last Summer".
        return bool(re.search(r'(?<![a-z])yui +summer(?![a-z])', title))
    if series == 'yui sim' and 'baby blue' in name:
        return 'baby blue' in title and bool(MODEL_RE.search(title))
    return bool(re.search(r'(?<![a-z])' + re.escape(name) + r'(?![a-z])', title)
                and (MODEL_RE.search(title) or series == 'yui'))


def queries(lead):
    if lead['series'].casefold() == 'artgravia':
        number = lead['volume']
        return [f'"ArtGravia" "{number}" "Yui"',
                f'"ArtGravia" "{number}" "유이"',
                f'"ArtGravia Vol.{number}" "沈惠星"']
    name = lead['work_name']
    if lead['series'] == 'Yui Sim':
        return [f'"Yui Sim" "{name}"', f'"심유이" "{name}"']
    return [f'"Yui" "{name}" photobook',
            f'"심유이" "{name}" 사진',
            f'"沈惠星" "{name}"']


def unwrap_link(link):
    """Reject search UI, credentials, inaccessible asset/archive links."""
    if not isinstance(link, str):
        return None
    if link.startswith('//'):
        link = 'https:' + link
    try:
        p = urlsplit(link)
        if p.scheme != 'https' or not p.hostname or p.username or p.password or p.port not in (None, 443):
            return None
        if p.hostname in SEARCH_HOSTS:
            q = parse_qs(p.query)
            nested = (q.get('uddg') or q.get('url') or q.get('u') or [''])[0]
            return unwrap_link(nested) if nested.startswith('https://') else None
        if re.search(r'\.(?:zip|rar|7z|pdf|exe)(?:$|\?)', p.path, re.I):
            return None
        if any(x in p.path.casefold() for x in ('/login', '/signin', '/captcha', '/challenge')):
            return None
        return urlunsplit(p._replace(fragment=''))
    except ValueError:
        return None


def hits_from_html(html, engine):
    soup = BeautifulSoup(html[:2_000_000], 'html.parser')
    css = 'li.b_algo h2 a[href]' if engine == 'bing' else 'a.result__a[href]'
    out, seen = [], set()
    for a in soup.select(css):
        url = unwrap_link(a.get('href'))
        label = a.get_text(' ', strip=True)
        if url and url not in seen:
            seen.add(url)
            parent = a.find_parent('li' if engine == 'bing' else 'div')
            summary = parent.get_text(' ', strip=True)[:350] if parent else label
            out.append({'url': url, 'title': label[:250], 'snippet': summary})
    return out


def title_supported(lead, result):
    text = compact(result.get('title', '') + ' ' + result.get('snippet', ''))
    if not MODEL_RE.search(text):
        return False
    if lead['series'].casefold() == 'artgravia':
        return 'artgravia' in text and bool(re.search(
            r'(?<!\d)' + str(lead['volume']) + r'(?!\d)', text))
    name = compact(lead.get('work_name', ''))
    return bool(name and re.search(r'(?<![a-z])' + re.escape(name) + r'(?![a-z])', text))


def search_one(session, lead, max_queries=3, timeout=17):
    candidates, seen, attempts = [], set(), []
    for q in queries(lead)[:max_queries]:
        for engine, (endpoint, parameter) in ENGINES.items():
            try:
                resp = session.get(endpoint, params={parameter: q},
                    headers={'User-Agent': UA, 'Accept': 'text/html'},
                    timeout=timeout, allow_redirects=False)
                content_type = resp.headers.get('Content-Type', '').lower()
                if resp.status_code != 200 or 'html' not in content_type:
                    attempts.append({'engine': engine, 'status': f'http_{resp.status_code}'})
                    continue
                body = resp.text
                if re.search('captcha|verify you are human|unusual traffic', body[:15000], re.I):
                    attempts.append({'engine': engine, 'status': 'search_access_boundary'})
                    continue
                hits = hits_from_html(body, engine)
                attempts.append({'engine': engine, 'status': 'ok', 'results': len(hits)})
                for hit in hits:
                    if hit['url'] not in seen and title_supported(lead, hit):
                        seen.add(hit['url'])
                        candidates.append({**hit, 'engine': engine, 'query': q,
                            'status': 'unverified_search_lead_not_downloaded'})
            except requests.RequestException as exc:
                attempts.append({'engine': engine, 'status': type(exc).__name__})
    return {'attempts': attempts, 'candidate_pages': candidates[:40]}


def discover(root=ROOT, leads_path=LEADS, search=False, max_works=30, client=None):
    src = json.loads(Path(leads_path).read_text(encoding='utf-8'))
    if src['model'] != 'yui' or src['schema_version'] != 1:
        raise ValueError('Unexpected visual lead registry')
    current = source_works(root)
    if not 1 <= max_works <= 100:
        raise ValueError('Bounded discovery budget required')
    session = client or requests.Session()
    rows = []
    for lead in src['works'][:max_works]:
        matches = [x for x in current if same_work(lead, x)]
        row = {**lead, 'catalogue_matches': matches,
               'classification': 'mapped_work_needs_photo_coverage_audit' if matches else 'unmapped_work_priority_search',
               'search_queries': queries(lead), 'images_new_saved': 0,
               'gallery_images_new': 0}
        if search and not matches:
            row['search_result'] = search_one(session, lead)
        rows.append(row)
    return {'schema_version': 1, 'generated_at': datetime.now(timezone.utc).isoformat(),
        'method': 'title-first-for-unregistered-works',
        'research_only_not_gallery_inventory': True,
        'total_works': len(rows),
        'unmapped_works': sum(not r['catalogue_matches'] for r in rows),
        'physical_new_files': 0, 'visible_new_files': 0,
        'works': rows}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--search', action='store_true', help='Ordinary public Bing and DuckDuckGo text search')
    ap.add_argument('--max-works', type=int, default=30)
    ap.add_argument('--out', type=Path, required=True)
    args = ap.parse_args()
    result = discover(search=args.search, max_works=args.max_works)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print('VISUAL_WORK_DISCOVERY', json.dumps({k: result[k] for k in
        ('total_works','unmapped_works','physical_new_files','visible_new_files')}, ensure_ascii=False))


if __name__ == '__main__':
    main()
