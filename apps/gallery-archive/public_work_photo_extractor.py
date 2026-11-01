"""Second-chance public photo extractor for confirmed model/work source pages.

No invented URLs, private API calls, browser authentication, or archive mutation.
Returns observed HTML image links; the caller must download/verify actual bytes.
"""
from __future__ import annotations

import ipaddress
import json
import re
from urllib.parse import urljoin, urlsplit

from bs4 import BeautifulSoup

MODEL_WORDS = {
    'yui': re.compile(r'(?<![a-z])yui(?![a-z])|심혜성|심유이|沈慧圣|super_yuisan', re.I),
    'mimmi': re.compile(r'(?<![a-z])mimmi(?![a-z])|밈미|밈미', re.I),
}
ARTICLE_SELECTORS = (
    '#powerbbsContent', '.portfolio-content', '.entry-content',
    '.post-content', '.post-body', '.article-content', '#post',
    '#content', '.gallery-content', '[itemprop=articleBody]',
    '.post', '.article', 'article', 'main', '[role=main]'
)
UNRELATED = re.compile(
    r'related|recommend|sidebar|comment|advert|banner|navigation|'
    r'footer|widget|popular|social-share|breadcrumb|more-posts', re.I)
NON_PHOTO = re.compile(
    r'logo|avatar|favicon|emoji|banner|placeholder|tracking|'
    r'pixel.gif|icon-|spinner|/ads?/', re.I)
PHOTO_EXT = re.compile(r'\.(?:jpe?g|png|webp|avif)(?:$|\?)', re.I)
BLOCKED_ORIGIN = {'cdn.jliji.com', 'metadata.google.internal', 'localhost'}
IMAGE_KEYS = ('data-original', 'data-full', 'data-large-file',
              'data-hires', 'data-image', 'data-fancybox-src',
              'data-lazy-src', 'data-src', 'src', 'srcset', 'data-srcset')


def ordinary_public_https_image(raw, page):
    """Allow ordinary public HTTPS image links without a hardcoded CDN list."""
    try:
        if not isinstance(raw, str) or not raw or len(raw) > 2100:
            return None
        url = urljoin(page, raw.strip())
        u = urlsplit(url)
        host = (u.hostname or '').lower().rstrip('.')
        if (u.scheme != 'https' or u.username or u.password or u.port not in (None, 443)
                or not host or host in BLOCKED_ORIGIN or u.fragment):
            return None
        if any(host.endswith(t) for t in
               ('.localhost', '.local', '.internal', '.invalid', '.test', '.example')):
            return None
        try:
            if not ipaddress.ip_address(host).is_global:
                return None
        except ValueError:
            if '.' not in host:
                return None
        if NON_PHOTO.search(u.path):
            return None
        # Image src/data-* attributes can have a content-addressed path with
        # no extension. Such objects must still decode as full photographs.
        return url
    except (ValueError, TypeError):
        return None


def _unrelated(node, article):
    for parent in (node, *node.parents):
        if parent is article:
            break
        tokens=' '.join(str(x) for x in parent.get('class', []))
        tokens += ' ' + str(parent.get('id') or '')
        if UNRELATED.search(tokens):
            return True
    return False


def _sections(soup):
    selected=[]
    for selector in ARTICLE_SELECTORS:
        for candidate in soup.select(selector):
            if candidate in selected or not candidate.find(['img', 'picture', 'source', 'a']):
                continue
            if any(candidate in parent.descendants for parent in selected):
                continue
            selected.append(candidate)
        if selected:
            return selected[:4]
    return []


def _observed(node, page):
    values=[]
    for attr in IMAGE_KEYS:
        value=node.get(attr)
        if not isinstance(value, str):
            continue
        if attr.endswith('srcset'):
            values.extend(part.strip().split()[0] for part in value.split(',')
                          if part.strip())
        elif attr == 'data-image' and value.lstrip().startswith('['):
            try:
                decoded=json.loads(value)
                if isinstance(decoded, list):
                    values.extend(x for x in decoded if isinstance(x, str))
            except (ValueError, TypeError):
                pass
        else:
            values.append(value)
    parent=node.find_parent('a')
    if parent and parent.get('href'):
        values.insert(0, parent['href'])
    for a in values:
        url=ordinary_public_https_image(a,page)
        if url:
            # An <a href> can target a post page rather than the full picture.
            # Enforce a photo-like path for anchor URLs.
            if a == (parent.get('href') if parent else None) and not PHOTO_EXT.search(urlsplit(url).path):
                continue
            yield url


def recover_public_work_photo_urls(raw, page, model, trusted_work=False):
    """Discover explicitly embedded photos even on unfamiliar publisher templates.

    The actual download still checks content decoding, bytes, SHA and owner
    photo identity; no result here is counted as a newly saved photo.
    """
    if not trusted_work:
        return [], 'not_registered_work'
    soup=BeautifulSoup(raw,'html.parser')
    titles=' '.join(tag.get_text(' ',strip=True)
                    for tag in soup.select('h1,title,h2[itemprop=headline]'))
    titles+=' '+' '.join(x.get('content', '') for x in soup.select(
        'meta[property="og:title"],meta[name="twitter:title"]'))
    if not MODEL_WORDS[model].search(titles):
        return [], 'model_identity_not_in_page_heading'
    sections=_sections(soup)
    if not sections:
        return [], 'no_scoped_article'
    urls=[]
    for section in sections:
        for node in section.select('img,source'):
            if _unrelated(node,section):
                continue
            for url in _observed(node,page):
                if url not in urls:
                    urls.append(url)
        # Direct public lightbox links can lack a nested img (gallery tiles).
        for node in section.select('a[href]'):
            if _unrelated(node,section):
                continue
            link=node.get('href','')
            url=ordinary_public_https_image(link,page)
            if url and PHOTO_EXT.search(urlsplit(url).path) and url not in urls:
                urls.append(url)
    return urls[:1800], 'article_image_attributes'
