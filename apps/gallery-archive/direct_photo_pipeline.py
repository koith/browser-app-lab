"""Collect normal public pages directly into resumable INDIVIDUAL owner files.

No photo ZIP, artifact, source hotlink, login, CAPTCHA, invented page/image URL,
or unverified overwrite. Cloud publication is a separate SHA-readback transaction.
"""
import argparse
from collections import defaultdict, Counter
from datetime import datetime, timezone
import hashlib
import ipaddress
from io import BytesIO
import json
from pathlib import Path
import re
import sys
from urllib.parse import urljoin, urlsplit, urlunsplit, parse_qsl, urlencode

from bs4 import BeautifulSoup
from PIL import Image, ImageStat
from photo_quality_evidence import preferred_pair, _decoded, _detail

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'apps/yui-gallery'))
from public_photo_archive import PublicSession,public_failure
from collect_private_batch import allowed_url, safe_reencoded_public_preview

MODEL_PATTERNS={'mimmi':re.compile(r'(?<![a-z])mimmi(?![a-z])|밈미|밈미',re.I),
                'yui':re.compile(r'(?<![a-z])yui(?![a-z])|유이|심혜성|심유이|沈慧圣|super_yuisan',re.I)}
PAGE_HOSTS={'djawaphoto.com','www.djawaphoto.com','cosplay.pixibb.com','sexy.pixibb.com','www.v2ph.com','v2ph.com',
            'blog.hacosta.co.jp','showartx.net','www.nicesss.com','www.gamersky.com','www.inven.co.kr','photo.inven.co.kr',
            'www.ajunews.com','sportsseoul.com','www.sportsseoul.com','crazygiant.imweb.me','teapawt.net','www.shypetal.com',
            # Public owner-work source hosts actually present in full-corpus manifests.
            # X/Twitter is deliberately excluded: generic timelines need author scoping.
            'www.junmeitu.com','www.kaizty.com','misskon.com','www.imgcup.com',
            '4kup.net','www.girl-atlas.com','www5.ajunews.com','v.daum.net',
            'www.huantuji.com','yuntu8.com','www.xiutu.me'}
SAME_HOST_WORK_IMAGE_SOURCES={'www.junmeitu.com','www.kaizty.com','misskon.com',
                              'www.imgcup.com','4kup.net','www.girl-atlas.com',
                              'www.huantuji.com','yuntu8.com','www.xiutu.me'}
# Registered public gallery sites frequently feature different people named Yui.
# We require an artist-specific identity AND the exact owner-work title token.
RESEARCH_WORK_HOSTS={'www.junmeitu.com','www.kaizty.com',
                     'misskon.com','www.imgcup.com'}
PUBLIC_STRONG_MODEL={
    'yui':re.compile(r'yui[ -]?sim|sim[ -]?yui|심혜성|심유이|沈慧圣|super_yuisan',re.I),
    'mimmi':re.compile(r'(?<![a-z])mimmi(?![a-z])|밈미',re.I)
}
CREATOR_ACCOUNTS={'yui':'super_yuisan','mimmi':'Mimmi_official'}
FORMATS={'JPEG':'jpg','PNG':'png','WEBP':'webp'}
KNOWN_ALTERNATE_EDITIONS={
    'pixibb-auto-creamsoda-mimmi-vol-2-neko-mimmi-62-photos-cosplay':'xiutu-public-1190160',
}


def safe_page(url):
    try:
        p=urlsplit(url)
        return (p.scheme=='https' and p.hostname in PAGE_HOSTS and not p.username and not p.password and p.port in (None,443)
                and (p.hostname!='teapawt.net' or p.path in {'/'+a for a in CREATOR_ACCOUNTS.values()}))
    except (ValueError,TypeError):return False


X_PUBLIC_HOSTS={'x.com','www.x.com','twitter.com','www.twitter.com'}
PUBLIC_SOURCE_DENIED_HOSTS={
    'localhost','metadata.google.internal','cdn.jliji.com'
}


def safe_registered_public_page(url,model=None):
    """Check any *already recorded* public work page, without a hostname allowlist.

    Only call this for owner-work/source manifest URLs or a same-work observed
    pagination link. No arbitrary Internet search URL becomes an owned work.
    """
    try:
        p=urlsplit(url)
        host=(p.hostname or '').lower().rstrip('.')
        if (p.scheme!='https' or p.username or p.password or p.port not in (None,443)
                or not host or host in PUBLIC_SOURCE_DENIED_HOSTS
                or len(url)>2200 or p.fragment):
            return False
        if any(host.endswith(s) for s in (
                '.local','.internal','.invalid','.test','.localhost','.example')):
            return False
        try:
            if not ipaddress.ip_address(host).is_global:
                return False
        except ValueError:
            if '.' not in host:
                return False
        if host=='teapawt.net':
            return safe_page(url)
        if host in X_PUBLIC_HOSTS:
            if model not in CREATOR_ACCOUNTS:
                return False
            # Public, explicitly recorded posts by the actual creator only.
            # Do not visit generic timelines, search pages or arbitrary actors.
            return bool(re.fullmatch(
                '/'+re.escape(CREATOR_ACCOUNTS[model])+r'/status/[0-9]{5,30}(?:/photo/[1-4])?/?',
                p.path,re.I))
        return True
    except (ValueError, TypeError):
        return False


def reviewed_direct_source(url, model):
    """Eligible *storage* origins. Other public hosts remain discovery leads."""
    from official_sample_recovery import _publisher_page
    from urllib.parse import urlsplit
    if _publisher_page(url):
        return True
    if not safe_registered_public_page(url,model):
        return False
    p=urlsplit(url)
    if p.hostname in X_PUBLIC_HOSTS:
        return True  # safe_registered_public_page already binds exact model author/status
    if (p.hostname=='teapawt.net' and model in CREATOR_ACCOUNTS
            and p.path=='/'+CREATOR_ACCOUNTS[model]):
        return True
    return False


def reviewed_direct_media(url, page, model):
    from official_sample_recovery import _publisher_page, _publisher_photo
    from urllib.parse import urlsplit
    if _publisher_page(page):
        return _publisher_photo(url)
    p=urlsplit(url)
    if (urlsplit(page).hostname in X_PUBLIC_HOSTS
            and reviewed_direct_source(page,model)):
        return (p.scheme=='https' and p.hostname=='pbs.twimg.com'
                and p.path.startswith('/media/') and not p.username
                and not p.password and not p.fragment)
    if (urlsplit(page).hostname=='teapawt.net' and
            reviewed_direct_source(page,model)):
        return (p.scheme=='https' and p.hostname in {'teapawt.net','pbs.twimg.com'}
                and not p.username and not p.password and not p.fragment)
    return False


def public_full_variant(url):
    p=urlsplit(url)
    if p.hostname=='upload3.inven.co.kr':
        return urlunsplit(p._replace(query=urlencode([(k,v) for k,v in parse_qsl(p.query) if k!='MW'])))
    return url



def rotated_registered_page_queue(primary, source_pages, max_pages, page_cycle=0):
    """Visit different already-registered pages across bounded repeated runs.

    Always fetch the exact verified primary work page. Only the order of
    explicitly recorded public source pages changes; no URLs are guessed.
    A zero cycle preserves historical order for offline tests and callers.
    """
    registered=list(dict.fromkeys([primary]+list(source_pages)))
    if not isinstance(page_cycle,int) or page_cycle<0:
        raise ValueError('page_cycle_must_be_nonnegative')
    if page_cycle==0 or len(registered)<=max_pages:
        return registered
    first,tail=registered[0],registered[1:]
    window=max(1,max_pages-1)
    offset=((page_cycle-1)*window)%len(tail)
    return [first]+tail[offset:]+tail[:offset]



def _work_token_matched_in_heading(raw,work_title,album_id,model):
    """A legacy source earns new-cut admission only for its named edition.

    A generic Yui/Mimmi timeline or photo article is not album identity proof.
    """
    soup=BeautifulSoup(raw,'html.parser')
    heading=' '.join(t.get_text(' ',strip=True) for t in soup.select('h1,title')).casefold()
    if not MODEL_PATTERNS[model].search(heading):
        return False
    # Neither the model name nor generic publishing terms distinguish a work.
    generic={'photo','photos','gallery','album','cosplay','image','images','public',
             'mimmi','yui','sim','vol','djawa','artgravia','edition','preview',
             'private','official','collection','part','the','and','set','girl'}
    tokens=re.findall(r'[a-z0-9]{4,}',str(work_title or '').casefold())
    tokens.extend(re.findall(r'[a-z]{4,}',str(album_id or '').casefold()))
    distinct=[t for t in dict.fromkeys(tokens) if t not in generic]
    return any(re.search(r'(?<![a-z0-9])'+re.escape(t)+r'(?![a-z0-9])',heading)
               for t in distinct)


def merge_owner_census_sources(books, owner, rows, model, safe_source=None):
    """Include every already-registered OWNER work with a public source.

    The benchmark used the full registered census, but the uploader read just a
    subset of manifests. This mismatch made verified detector improvements
    appear as zero new candidates during actual collection.
    """
    allowed=safe_source or (lambda u:safe_registered_public_page(u,model))
    known={a['id']:a for a in owner['albums']}
    stats={'census_owner_work_count':0,'census_eligible_work_count':0,
           'unowned_registered_works_with_source':0,
           'newly_scheduled_unowned_works':0,
           'newly_scheduled_work_count':0,'additional_registered_pages':0,
           'registered_source_rejected':0}
    for row in rows:
        if row.get('model')!=model or row.get('kind')!='work':
            continue
        aid=row['id']
        if not re.fullmatch(r'[a-z0-9][a-z0-9-]{1,100}',aid):
            continue
        owner_work=aid in known
        # Unowned work IDs can be created ONLY from an existing real named-work
        # manifest, never from a suggested model-alias or a guessed photo URL.
        if not owner_work and not row.get('manifest_sources'):
            continue
        if owner_work:
            stats['census_owner_work_count']+=1
        candidate=list(dict.fromkeys(row.get('urls') or []))
        verified=[u for u in candidate if allowed(u)]
        stats['registered_source_rejected']+=len(candidate)-len(verified)
        if not verified:
            continue
        if owner_work:
            stats['census_eligible_work_count']+=1
        else:
            stats['unowned_registered_works_with_source']+=1
        if aid in books:
            book=books[aid]
            before=set([book['source']]+book.get('source_pages',[]))
            book['source_pages']=list(dict.fromkeys(
                list(book.get('source_pages',[]))+verified))
            stats['additional_registered_pages']+=len(
                set(book['source_pages'])-before)
        else:
            held=known.get(aid,{})
            books[aid]={'id':aid,'title':held.get('title') or row.get('title') or aid,
                        'source':verified[0],'source_pages':verified[1:],
                        'curated_images_only':owner_work,
                        'census_existing_owner':owner_work,
                        'census_new_work':not owner_work}
            if owner_work:
                stats['newly_scheduled_work_count']+=1
            else:
                stats['newly_scheduled_unowned_works']+=1
    return stats


def _photo_asset_group(url):
    """Canonicalize observed resized renditions without inventing a photo URL."""
    p=urlsplit(url)
    canonical=re.sub(r'-\d{2,5}x\d{2,5}(?=\.(?:jpe?g|png|webp)$)',
                     '',p.path,flags=re.I)
    return (p.hostname,canonical)


def verified_alternative_candidates(raw,page,model,baseline,known_urls,
                                    rendered=(),scrapy_extractor=None,
                                    trusted_registered_page=False):
    """Turn real Scrapy/Chromium findings into bounded *download candidates*.

    Existing owner/historical asset identities take precedence. Discovery is
    unavailable for generic creator timelines. Older curated source pages may
    admit NEW candidates only when their actual headline identifies the model
    and the work is already present in the private owner index.
    All accepted bytes still require inspect(), owner SHA readback and gallery QA.
    """
    if not (safe_page(page) or trusted_registered_page) or urlsplit(page).hostname in (
            'teapawt.net',*X_PUBLIC_HOSTS):
        return [],'specialized_author_only'
    soup=BeautifulSoup(raw,'html.parser')
    heading=' '.join(tag.get_text(' ',strip=True) for tag in soup.select('h1,title'))
    if not MODEL_PATTERNS[model].search(heading):
        return [],'no_headline_model_identity'
    if urlsplit(page).hostname in RESEARCH_WORK_HOSTS:
        if not PUBLIC_STRONG_MODEL[model].search(heading):
            return [],'ambiguous_model_identity_on_research_host'
    if scrapy_extractor is None:
        from collector_full_compare import independent_scrapy_extract
        scrapy_extractor=independent_scrapy_extract
    discovered,status=scrapy_extractor(raw,page,model)
    from collector_full_compare import alternative_safe_photo
    from public_work_photo_extractor import (
        recover_public_work_photo_urls, ordinary_public_https_image)
    # The old selector missed unfamiliar article templates, original lightbox
    # URLs and image CDN endpoints without .jpg suffixes. Only image attributes
    # actually present in this registered page can extend the CDN set.
    recovered,recovery_status=recover_public_work_photo_urls(
        raw,page,model,trusted_work=True)
    observed=set(recovered)
    prior={_photo_asset_group(u) for u in list(baseline)+list(known_urls)}
    groups={}
    for u in list(discovered)+list(rendered)+recovered:
        if not ordinary_public_https_image(u,page):
            continue
        approved,_=allowed_url(u)
        p=urlsplit(u)
        # Previously unknown CDN domains are accepted ONLY when a photo link
        # appears inside the model-scoped article/picture element, not because
        # the domain was included in a benchmark or search result.
        if not approved and u not in observed and not (
            alternative_safe_photo(u) and p.hostname==urlsplit(page).hostname
            and p.hostname in SAME_HOST_WORK_IMAGE_SOURCES):
            continue
        if p.hostname in ('djawaphoto.com','www.djawaphoto.com') and not p.path.startswith('/wp-content/uploads/'):
            continue
        key=_photo_asset_group(u)
        if key in prior:continue
        # Prefer a publicly observed native asset over a WordPress size variant
        # of that SAME URL, never fabricate a suffix-free URL.
        resized=bool(re.search(r'-\d{2,5}x\d{2,5}(?=\.)',p.path,re.I))
        rank=(not resized,len(p.path))
        if key not in groups or rank>groups[key][0]:
            groups[key]=(rank,u)
    return [x[1] for x in groups.values()],status


def same_variant(old_raw,new_raw):
    """Same observed public asset only; never identify people or merge works."""
    with Image.open(BytesIO(old_raw)) as old, Image.open(BytesIO(new_raw)) as new:
        if abs((old.width/old.height)/(new.width/new.height)-1)>.01:return False
        a=old.convert('RGB').resize((64,64));b=new.convert('RGB').resize((64,64))
        from PIL import ImageChops
        return max(ImageStat.Stat(ImageChops.difference(a,b)).mean)<=5


def in_excluded_article_section(tag,article):
    """Only reject related/advert/sidebar parents *inside* this work article.

    Many WordPress pages have <body class="sidebar-right"> globally. Looking
    at every ancestor mistakenly rejects every real photo in the main article.
    """
    for parent in tag.parents:
        if parent is article:break
        if any(re.search(r'related|recommend|comment|advert|sidebar',str(c),re.I)
               for c in parent.get('class',[])):
            return True
    return False


def page_images(raw,url,model):
    if urlsplit(url).hostname in X_PUBLIC_HOSTS:
        if not safe_registered_public_page(url,model):
            return [],[],'unrelated_social_account_rejected'
        # Only media embedded in the author's actual public status article.
        # A sign-in wall is not a public photograph.
        account=CREATOR_ACCOUNTS[model]
        soup=BeautifulSoup(raw,'html.parser')
        originals=[]
        for article in soup.select('article'):
            identity=bool(article.select(
                'a[href="/'+account+'"],a[href^="/'+account+'/"]'))
            identity=identity or bool(re.search(
                r'(?<![a-z0-9_])@'+re.escape(account)+r'(?![a-z0-9_])',
                article.get_text(' ',strip=True),re.I))
            if not identity:
                continue
            for tag in article.select('img[src],img[data-src],source[srcset]'):
                values=[tag.get('src'),tag.get('data-src')]
                values.extend(part.strip().split()[0]
                              for part in (tag.get('srcset') or '').split(',')
                              if part.strip())
                for value in values:
                    if not value:
                        continue
                    u=urljoin(url,value)
                    p=urlsplit(u)
                    if (p.scheme=='https' and p.hostname=='pbs.twimg.com'
                            and p.path.startswith('/media/') and u not in originals):
                        originals.append(u)
        return originals,[],'scoped_public_page' if originals else 'no_public_photos'
    if urlsplit(url).hostname=='teapawt.net':
        account=CREATOR_ACCOUNTS[model]
        if urlsplit(url).path!='/'+account:return [],[],'different_creator_account_rejected'
        from collect_teapawt_public import public_images_from_author
        # Use exact media URLs exposed by the normal page, preserving its
        # original-size query. No guessed CDN hosts, protected API or login.
        urls,next_page,cards=public_images_from_author(raw,{'account':account},url)
        return urls,[next_page] if next_page else [],'scoped_public_page' if cards else 'missing_model_context'
    soup=BeautifulSoup(raw,'html.parser')
    if urlsplit(url).hostname in ('www.v2ph.com','v2ph.com'):
        # Ordinary publicly visible album page only. Pagination past its
        # login boundary must stop: never guess signed assets or fetch members'
        # galleries through an alternate endpoint.
        title=soup.select_one('h1')
        heading=title.get_text(' ',strip=True) if title else ''
        if not MODEL_PATTERNS[model].search(heading):
            return [],[],'missing_model_context'
        if re.search(r'need to log in to view more|login to view more|请登录|ログインして',soup.get_text(' ',strip=True),re.I):
            return [],[],'login_required_for_additional_pages'
        selected=[]
        seen=set()
        def candidate(raw_link):
            full=urljoin(url,str(raw_link or '').strip())
            p=urlsplit(full)
            # V2PH's public photo CDN is distinct from its related-album
            # thumbnails. Admit only observed individual-image URLs.
            if (p.scheme!='https' or p.hostname!='cdn.v2ph.com' or p.query
                    or p.fragment or not re.fullmatch(r'/photos/[A-Za-z0-9_-]{8,80}\.(?:jpg|jpeg|png|webp)',p.path,re.I)):
                return
            if full not in seen:
                seen.add(full);selected.append(full)
        for a in soup.select('a[href]'):
            if a.find_parent(class_=re.compile(r'related|recommend|sidebar',re.I)):
                continue
            if a.find('img') is not None:
                candidate(a.get('href'))
        # Covers sites that expose native photo src on the image node itself.
        for img in soup.select('img'):
            if img.find_parent(class_=re.compile(r'related|recommend|sidebar',re.I)):
                continue
            for key in ('data-original','data-src','src'):
                candidate(img.get(key))
        more=[]
        here=urlsplit(url)
        for a in soup.select('a[href]'):
            target=urljoin(url,a['href']);q=urlsplit(target)
            if q.scheme!='https' or q.hostname!=here.hostname or q.path!=here.path:
                continue
            params=dict(parse_qsl(q.query))
            if set(params)!={'page'} or not params['page'].isdigit():
                continue
            page_number=int(params['page'])
            if 2<=page_number<=60 and target!=url and target not in more:
                more.append(target)
        # No source identity/album content should be inferred from gallery count.
        return selected,more,'scoped_public_page' if selected else 'no_public_photos'
    if urlsplit(url).hostname=='www.nicesss.com':
        # Independent public previews for Yui ArtGravia Vol.677. A different
        # origin may be usable after another origin returns 403. Only exact
        # asset URLs observed on this single public post are admitted.
        if model!='yui' or urlsplit(url).path!='/archives/mij/artgravia/469248.html':
            return [],[],'unscoped_page_rejected'
        heading=' '.join(h.get_text(' ',strip=True) for h in soup.select('h1,title'))
        if not (MODEL_PATTERNS['yui'].search(heading) and 'artgravia' in heading.casefold()
                and re.search(r'(?<!\d)677(?!\d)',heading)):
            return [],[],'missing_model_or_volume_context'
        article=(soup.select_one('.entry-content') or soup.select_one('article')
                 or soup.select_one('.article-content'))
        if article is None:return [],[],'unscoped_page_rejected'
        approved={
            'https://www.nicewww.com/wp-content/uploads/2026/05/1778813739-c81e728d9d4c2f6.jpg',
            'https://www.nicewww.com/wp-content/uploads/2026/05/1778813742-eccbc87e4b5ce2f.jpg',
            'https://www.nicewww.com/wp-content/uploads/2026/05/1778813743-a87ff679a2f3e71.jpg',
            'https://www.nicewww.com/wp-content/uploads/2026/05/1778813745-e4da3b7fbbce234.jpg',
        }
        found=[]
        for img in article.select('img'):
            if in_excluded_article_section(img,article):
                continue
            for key in ('data-original','data-src','src'):
                value=img.get(key)
                if value:
                    full=urljoin(url,value)
                    if full in approved and full not in found:found.append(full)
            parent=img.find_parent('a')
            if parent and parent.get('href'):
                full=urljoin(url,parent.get('href'))
                if full in approved and full not in found:found.append(full)
        return found,[],'scoped_public_page' if found else 'no_public_photos'
    if urlsplit(url).hostname=='showartx.net':
        # Model+work scoped regular public preview gallery: do not enumerate
        # photo numbers or access the paid full edition. These prefix mappings
        # are grounded in individually observed public <img> src attributes.
        work=re.fullmatch(r'/artgravia-vol-(\d{2,4})-yui/?',urlsplit(url).path,re.I)
        creator_work=re.fullmatch(r'/yui-([a-z0-9-]+)/?',urlsplit(url).path,re.I)
        named={
            'asuna-qipao':('Asuna Qipao','Yui_Asuna-Qipao_'),
            'become-beautiful':('Become Beautiful','yui_beautiful_'),
            'meow':('Meow','Yui_Meow_'),
            'night-cat':('Night Cat','NightCat_'),
            'night-training':('Night Training','Yui_Night-Training_'),
            'pure':('Pure','Yui_pure_'),
            'summer':('Summer','Yui_Sum_'),
        }
        if model!='yui' or not (work or creator_work and creator_work.group(1) in named):
            return [],[],'unscoped_page_rejected'
        soup=BeautifulSoup(raw,'html.parser')
        heading=' '.join(h.get_text(' ',strip=True) for h in soup.select('h1,title'))
        if not MODEL_PATTERNS[model].search(heading):
            return [],[],'missing_model_or_volume_context'
        if work:
            volume=int(work.group(1))
            expected_title='artgravia'
            file_prefix='ART_'+str(volume)+'_'
            title_supported=('artgravia' in heading.casefold() and
                    bool(re.search(r'(?<!\d)'+str(volume)+r'(?!\d)',heading)))
        else:
            expected_title,file_prefix=named[creator_work.group(1)]
            title_supported=(expected_title.casefold() in heading.casefold())
        if not title_supported:return [],[],'missing_model_or_volume_context'
        article=soup.select_one('article') or soup.select_one('.entry-content')
        if article is None:return [],[],'unscoped_page_rejected'
        chosen={}
        for img in article.select('img'):
            if in_excluded_article_section(img,article):
                continue
            links=[img.get('data-original'),img.get('data-src'),img.get('src')]
            anchor=img.find_parent('a')
            if anchor:links.insert(0,anchor.get('href'))
            for link in links:
                if not link:continue
                candidate=urljoin(url,link);p=urlsplit(candidate)
                if p.scheme!='https' or p.hostname!='showartx.net' or p.query or p.fragment:
                    continue
                m=re.fullmatch(r'/wp-content/uploads/\d{4}/\d{2}/'+re.escape(file_prefix)+r'(\d{1,3})(?:-(\d{2,5})x\d{2,5})?\.jpg',p.path,re.I)
                if not m:continue
                number=int(m.group(1));native=m.group(2) is None
                if number not in chosen or native and not chosen[number][0]:
                    chosen[number]=(native,candidate)
        return [chosen[k][1] for k in sorted(chosen)],[],'scoped_public_page' if chosen else 'no_public_photos'
    if urlsplit(url).hostname=='www.shypetal.com':
        # The ordinary page declares its individual lightbox image list. Read
        # that public JSON only; never click its compressed-download controls.
        title=' '.join(t.get_text(' ',strip=True) for t in soup.select('h1,title'))
        if not MODEL_PATTERNS[model].search(title):return [],[],'missing_model_context'
        declaration=soup.select_one('[data-images]')
        try:images=json.loads(declaration['data-images']) if declaration else []
        except (TypeError,ValueError):return [],[],'invalid_public_image_declaration'
        if not isinstance(images,list) or not 1<=len(images)<=500:return [],[],'invalid_public_image_declaration'
        accepted=[];folders=set()
        for image in images:
            if not isinstance(image,str):return [],[],'invalid_public_image_declaration'
            p=urlsplit(image)
            if (p.scheme!='https' or p.hostname!='image.shypetal.com' or p.username or p.password
                    or p.port not in (None,443) or p.query or p.fragment
                    or not re.fullmatch(r'/image/[^/]+/ShyPetal\.com@-\d{1,4}\.webp',p.path)):
                return [],[],'invalid_public_image_declaration'
            folders.add(p.path.rsplit('/',1)[0]);accepted.append(image)
        if len(folders)!=1:return [],[],'mixed_public_editions_rejected'
        return list(dict.fromkeys(accepted)),[],'scoped_public_page'
    article=(soup.select_one('#powerbbsContent') or soup.select_one('.portfolio-content') or soup.select_one('article')
             or soup.select_one('.entry-content') or soup.select_one('main'))
    if article is None:return [],[], 'unscoped_page_rejected'
    headings=soup.select('h1,title');identity=' '.join(t.get_text(' ',strip=True) for t in headings)+' '+article.get_text(' ',strip=True)
    if not MODEL_PATTERNS[model].search(identity):return [],[],'missing_model_context'
    candidates={};order=[]
    for tag in article.select('a[href],img,source'):
        # Related posts, recommended models and comments do not belong to work.
        if in_excluded_article_section(tag,article):continue
        attrs=('href',) if tag.name=='a' else ('data-original','data-full','data-large-file','data-src','data-lazy-src','srcset','data-srcset','src')
        for attr in attrs:
            for item in (tag.get(attr,'').split(',') if 'srcset' in attr else [tag.get(attr,'')]):
                if not item.strip():continue
                bits=item.strip().split();image=urljoin(url,bits[0]);p=urlsplit(image)
                # Inven's documented public image-width parameter changes only
                # resizing of the same public object, never access or identity.
                # Its unscaled 3072x4096 object was compared with the 800px view.
                if p.hostname=='upload3.inven.co.kr' and soup.select_one('#powerbbsContent'):
                    image=public_full_variant(image)
                    p=urlsplit(image)
                allowed,_=allowed_url(image)
                if not allowed or not re.search(r'\.(jpe?g|png|webp)$',p.path,re.I):continue
                if re.search(r'logo|avatar|emoji|banner|favicon|placeholder|spacer|tracking',p.path,re.I):continue
                derivative=re.search(r'-(\d{2,5})x(\d{2,5})(?=\.)',p.path)
                identity=re.sub(r'-\d{2,5}x\d{2,5}(?=\.)','',p.path)
                key=(p.hostname,identity)
                descriptor=int(bits[1][:-1]) if len(bits)>1 and bits[1].endswith('w') and bits[1][:-1].isdigit() else 0
                resized=bool(derivative) or any(k.casefold() in {'w','width','h','height','mw','resize'} for k,_ in parse_qsl(p.query))
                # An arbitrary numeric bonus let a 3000px resize beat its
                # observed native original. Rank native identity first.
                score=(not resized,descriptor,int(derivative[1])*int(derivative[2]) if derivative else 0)
                if key not in candidates:order.append(key)
                if key not in candidates or score>candidates[key][0]:candidates[key]=(score,image)
    links=[]
    here=urlsplit(url)
    for a in soup.select('a[href]'):
        target=urljoin(url,a['href']);there=urlsplit(target)
        label=a.get_text(' ',strip=True).casefold()
        if not safe_page(target) or there.hostname!=here.hostname:continue
        same_collection=(there.path.rstrip('/')==here.path.rstrip('/') or
                         there.path.startswith(here.path.rstrip('/')+'/'))
        if same_collection and (a.get('rel')==['next'] or label in ('next','older','다음','下一页','›','»') or label.isdigit()):
            if target!=url and target not in links:links.append(target)
    return [candidates[k][1] for k in order],links,'scoped_public_page'


def inspect(raw):
    if not 5000<=len(raw)<=24_000_000:raise ValueError('source_size_outside_bounds')
    with Image.open(BytesIO(raw)) as im:im.verify()
    with Image.open(BytesIO(raw)) as im:
        im.load();w,h=im.size;ext=FORMATS.get(im.format)
        if not ext or min(w,h)<300 or w*h>40_000_000:raise ValueError('not_full_photo_dimensions_or_format')
        preview=im.convert('RGB');preview.thumbnail((520,520),Image.Resampling.LANCZOS)
        # A flat error image can be a perfectly valid 1024px JPEG.
        if max(ImageStat.Stat(preview.resize((32,32))).stddev)<3:raise ValueError('flat_placeholder')
        data=BytesIO();preview.save(data,format='WEBP',lossless=True,method=4)
        return {'sha256':hashlib.sha256(raw).hexdigest(),'bytes':len(raw),'width':w,'height':h,'extension':ext},data.getvalue(),im.format


def measured_photo_quality(raw, photo):
    """Inspect genuine decoded pixels; do not equate dimensions with sharpness.

    A heuristic blur/upscale flag is not a rejection or a watermark detector.
    The same-photo optical comparator decides any actual replacement.
    """
    im=_decoded(raw)
    detail=_detail(im)
    pixels=max(1,photo['width']*photo['height'])
    density=round(8*photo['bytes']/pixels,4)
    suspect=(pixels>=2_000_000 and density<0.42 and detail<0.035)
    return {
        'actual_decoded_megapixels':round(pixels/1_000_000,3),
        'original_bytes':photo['bytes'],
        'encoded_bits_per_pixel':density,
        'real_pixel_detail_index':detail,
        'possible_artificial_upscale_or_blur':suspect,
        'watermark_status':'unverified',
        'comparison_rule':'optical_detail_first_then_verified_watermark_absence',
        'metrics_are_heuristic':True
    }


def atomic_bytes(path,data):
    path.parent.mkdir(parents=True,exist_ok=True)
    if path.exists():
        if path.read_bytes()!=data:raise ValueError('Existing file cannot be overwritten')
        return
    tmp=path.with_name(path.name+'.pending');tmp.write_bytes(data);tmp.replace(path)


def collect(root,model,owner,out,max_new=180,max_pages=24,client=None,focused_only=False,album_ids=None,page_cycle=0,alternative_engines=False,render_budget=8,reverse_evidence=None,reviewed_source_only=False):
    root=Path(root);out=Path(out)
    if owner.get('model')!=model or owner.get('schema_version')!=1 or not owner.get('albums'):
        raise ValueError('Current owner catalog required; do not assume empty archive')
    base=root/'apps'/(model+'-gallery')
    inputs=(['official-previews.json','v2ph-actor-previews.json','pixibb-public-previews.json'] if model=='mimmi' else ['additional-source-albums.json'])+['public-work-pages.json']
    old_albums={a['id']:a for a in owner['albums']};saved_sha={p['sha256'] for a in owner['albums'] for p in a['images']}
    # A locally visible GitHub Pages copy is not proof of a remote TeraBox
    # original+preview pair. Keep both ledgers separate for official recovery.
    owner_remote_sha=set(saved_sha)
    public=json.loads((base/'stored-albums.json').read_text())
    reference_paths={}
    for album in public['albums']:
        for photo in album['images']:
            path=(base/str(photo.get('url',''))).resolve()
            if path.is_relative_to(base.resolve()) and str(photo.get('url','')).startswith('stored-albums/') and path.is_file():
                reference_paths[photo['sha256']]=path
    saved_sha.update(p['sha256'] for a in public['albums'] for p in a['images'])
    books={};historic={}
    for filename in inputs:
        path=base/filename
        if not path.exists():continue
        for a in json.loads(path.read_text()).get('albums',[]):
            for n,p in enumerate(a.get('samples') or a.get('images') or [],1):
                if p.get('url'):
                    historic[(a['id'],p['url'])]={**p,'number':p.get('number',n)}
                    full=public_full_variant(p['url'])
                    if full!=p['url']:historic[(a['id'],full)]={**p,'number':p.get('number',n),'public_full_variant':True}
            # The original Yui ledger records observed pages as source_pages,
            # while newer reviewed entries have a primary source. Do not silently
            # omit that entire ledger, invent a URL, or widen its image scope.
            legacy=not a.get('source')
            pages=[u for u in a.get('source_pages',[]) if safe_registered_public_page(u,model)]
            source=a.get('source') or next(iter(pages),None)
            if not source or not safe_registered_public_page(source,model):continue
            if not re.fullmatch(r'[a-z0-9][a-z0-9-]{1,100}',str(a.get('id',''))):continue
            # A shared event/report can mention Yui while showing other models.
            # Legacy records admit only already curated image URLs in an existing
            # owner work. New URLs need a separate, explicitly reviewed source.
            if legacy and a['id'] not in old_albums:continue
            if KNOWN_ALTERNATE_EDITIONS.get(a['id']) in old_albums:continue
            a={**a,'source':source,'source_pages':pages,'curated_images_only':legacy}
            if a['id'] in books:
                prior=books[a['id']]
                prior['source_pages']=list(dict.fromkeys(prior.get('source_pages',[])+[source]+a.get('source_pages',[])))
                prior['curated_images_only']=prior['curated_images_only'] and legacy
                if a.get('visual_reference_required'):prior.update(a)
            else:books[a['id']]=dict(a)
    from collector_full_census import census
    registry=root/'apps/gallery-archive/global_source_registry.json'
    if registry.exists():
        source_census=census(root)
        source_scope=merge_owner_census_sources(
            books,owner,source_census['targets'],model)
    elif root.resolve()==ROOT.resolve():
        raise ValueError('Real registry missing: cannot assert exhaustive owner work coverage')
    else:
        # Tiny synthetic test roots need not reproduce every research manifest.
        source_scope={'census_status':'synthetic_fixture_without_registry'}
    reverse_counts={'reverse_source_pages_admitted':0,
                    'reverse_works_with_source':0,
                    'reverse_unverified_targets_rejected':0}
    if reverse_evidence is not None and Path(reverse_evidence).exists():
        evidence=json.loads(Path(reverse_evidence).read_text(encoding='utf-8'))
        if evidence.get('model')!=model:
            raise ValueError('Reverse-source model mismatch')
        for target in evidence.get('targets',[]):
            aid=target.get('id')
            if not isinstance(aid,str) or not re.fullmatch(
                    r'[a-z0-9][a-z0-9-]{1,100}',aid):
                reverse_counts['reverse_unverified_targets_rejected']+=1
                continue
            links=list(dict.fromkeys(
                u for u in target.get('urls',[])
                if safe_registered_public_page(u,model)))
            if not links:
                reverse_counts['reverse_unverified_targets_rejected']+=1
                continue
            if aid in books:
                book=books[aid]
                book['source_pages']=list(dict.fromkeys(
                    book.get('source_pages',[])+links))
            else:
                held=old_albums.get(aid,{})
                book={'id':aid,'title':held.get('title') or target.get('title') or aid,
                      'source':links[0],'source_pages':links[1:],
                      'curated_images_only':bool(held),
                      'census_new_work':not bool(held)}
                books[aid]=book
            book['reverse_unverified_pages']=list(dict.fromkeys(
                book.get('reverse_unverified_pages',[])+links))
            reverse_counts['reverse_works_with_source']+=1
            reverse_counts['reverse_source_pages_admitted']+=len(links)
    source_scope.update(reverse_counts)
    # Prioritize exact, already-SHA-recorded publisher sample URLs that have
    # no matching byte variant in the real owner archive. A duplicate URL with
    # two historical hashes counts as ONE possible photo, never two.
    from official_sample_recovery import (
        missing_verified_publisher_samples, matching_recorded_variant)
    official_gaps=missing_verified_publisher_samples(base,owner,model)
    source_scope['known_official_unarchived_unique_urls']=sum(
        len(rows) for rows in official_gaps.values())
    if reviewed_source_only:
        approved=[]
        for book in books.values():
            proposed=list(dict.fromkeys(
                [book['source']]+book.get('source_pages',[])))
            approved_pages=[u for u in proposed if reviewed_direct_source(u,model)]
            if not approved_pages:
                continue
            book['source']=approved_pages[0]
            book['source_pages']=approved_pages[1:]
            approved.append(book)
        books={book['id']:book for book in approved}
        source_scope['reviewed_storage_scope_works']=len(books)
        source_scope['unreviewed_pages_are_discovery_leads_not_storage']=True
    print('PRODUCTION_REGISTERED_WORK_COVERAGE',model,
          json.dumps(source_scope,ensure_ascii=False),flush=True)
    client=client or PublicSession(delay=.8)
    if not isinstance(render_budget,int) or not 0<=render_budget<=50:
        raise ValueError('Invalid bounded Chromium page budget')
    browser=None
    if alternative_engines:
        import scrapy  # Real extractor dependency is required, not a silent fallback
    if alternative_engines and render_budget:
        from collector_full_compare import LiveBrowser
        browser=LiveBrowser(enabled=True)
    rendered_pages=0
    results=[];new_albums=[];new_total=0;downloaded_now=0;seen_urls=set();seen_sha=set(saved_sha)
    official_staged_sha=set()
    resumed=defaultdict(list)
    journal=out/'journal.jsonl'
    if journal.exists():
        for line in journal.read_text().splitlines():
            entry=json.loads(line);row=entry.get('photo')
            if not row or row['sha256'] in seen_sha:continue
            for field,digest,size in [('key','sha256','bytes'),('preview','preview_sha256','preview_bytes')]:
                name=row[field]
                if '..' in Path(name).parts or Path(name).is_absolute():raise ValueError('Unsafe resume path')
                data=(out/name).read_bytes()
                if len(data)!=row[size] or hashlib.sha256(data).hexdigest()!=row[digest]:raise ValueError('Staged file corrupted during interruption')
            resumed[entry['album']].append(row);seen_sha.add(row['sha256']);seen_urls.add(entry['source']);new_total+=1
    selected=set(album_ids or [])
    if selected and (len(selected)>12 or any(not re.fullmatch(r'[a-z0-9][a-z0-9-]{1,100}',v) for v in selected)):
        raise ValueError('Invalid bounded album selection')
    books=sorted((a for a in books.values()
                  if (not focused_only or a.get('visual_reference_required'))
                  and (not selected or a['id'] in selected)),
        key=lambda a:(0 if official_gaps.get(a['id']) else 1,
                      a.get('priority',100),
                      len(old_albums.get(a['id'],{}).get('images',[])),a['id']))
    if set(resumed)-{a['id'] for a in books}:
        raise ValueError('Resumed work no longer in source scope; preserve staged files for review')
    for book in books:
        if new_total>=max_new and not resumed.get(book['id']):continue
        aid=book['id'];previous=old_albums.get(aid,{}).get('images',[]);occupied={p['number'] for p in previous};next_number=max(occupied,default=0)+1
        if book.get('storage_verification_hold') is True:
            results.append({'id':aid,'individual_files_saved':0,'storage_verification_required':True,
                'source_not_redownloaded':True,'failures':['owner_provider_verification_required']})
            print('OWNER_WORK_STORAGE_VERIFICATION_HELD',model,aid,'SOURCE_NOT_REDOWNLOADED',True,flush=True)
            continue
        if book.get('visual_reference_required'):
            if resumed.get(aid):raise ValueError('Visual-edition resume requires finalized work transaction')
            from visual_public_work import collect_work
            work,info=collect_work(book,previous,client,out,max_new-new_total,seen_sha,model,reference_paths=reference_paths)
            if work:
                new_albums.append(work);new_total+=len(work['images']);downloaded_now+=len(work['images'])
            results.append(info)
            print('VISUAL_PUBLIC_WORK',model,aid,json.dumps({k:v for k,v in info.items()
                if k not in ('observed_filename_numbers','saved_cut_correspondence')},ensure_ascii=False),flush=True)
            continue
        images=list(resumed.get(aid,[]));occupied.update(p['number'] for p in images);next_number=max(occupied,default=0)+1
        alt_photo_urls=set()
        alt_candidate_count=0
        alt_new_staged=0
        rendered_work_pages=0
        blocked_origin_pages=0
        known_work_urls=[url for work_id,url in historic if work_id==aid]

        queue=rotated_registered_page_queue(book['source'],[u for u in book.get('source_pages',[]) if safe_registered_public_page(u,model)],max_pages,page_cycle);visited=set();errors=[];candidate_count=0;unreviewed_count=0
        known_official_saved=0
        for gap in official_gaps.get(aid,[]):
            if new_total>=max_new:
                break
            url=gap['url']
            if url in seen_urls:
                continue
            if not reviewed_direct_source(gap['publisher_page'],model):
                continue
            if not reviewed_direct_media(url,gap['publisher_page'],model):
                continue
            seen_urls.add(url)
            try:
                raw=client.get(url).content
                p,preview,fmt=inspect(raw)
                if not matching_recorded_variant(
                        raw,p,gap['recorded_variants']):
                    errors.append({'url':url,'reason':'official_publisher_bytes_not_same_sha_as_verified_history'})
                    continue
                # Exact owner-private bytes determine storage completion.
                # Public Pages may already show this SHA without an owner
                # TeraBox original; we still have to archive that photo pair.
                if (p['sha256'] in owner_remote_sha
                        or p['sha256'] in official_staged_sha):
                    continue
                quality=measured_photo_quality(raw,p)
                number=next_number
                next_number+=1
                occupied.add(number)
                seen_sha.add(p['sha256'])
                official_staged_sha.add(p['sha256'])
                name=f'{number:05d}-{p["sha256"][:16]}'
                original=f'originals/{aid}/{name}.{p.pop("extension")}'
                thumbnail=f'previews/{aid}/{name}.webp'
                atomic_bytes(out/original,raw)
                atomic_bytes(out/thumbnail,preview)
                row={**p,'number':number,'key':original,'preview':thumbnail,
                     'preview_sha256':hashlib.sha256(preview).hexdigest(),
                     'preview_bytes':len(preview),
                     'measured_image_quality':quality,
                     'numbering_provenance':'official_source_unique_url_append_not_publisher_sequence'}
                images.append(row)
                new_total+=1
                downloaded_now+=1
                known_official_saved+=1
                with journal.open('a') as log:
                    log.write(json.dumps({
                        'album':aid,'number':number,'source':url,
                        'photo':row,'remote_verified':False})+'\n')
            except Exception as exc:
                errors.append({'url':url,'reason':type(exc).__name__,**public_failure(exc)})
        if known_official_saved:
            print('OFFICIAL_UNARCHIVED_SAMPLE_STAGED',model,aid,
                  known_official_saved,flush=True)
        while queue and len(visited)<max_pages and new_total<max_new:
            page=queue.pop(0)
            if page in visited:continue
            origin=urlsplit(page).scheme+'://'+urlsplit(page).netloc
            if origin in getattr(client,'blocked_origins',set()):
                # The crawler has already observed an access/rate/legal block.
                # Skip this host in the current run; spend remaining work
                # budget on other explicitly registered public sources.
                blocked_origin_pages+=1
                continue
            visited.add(page)
            try:
                response=client.get(page);urls,more,status=page_images(response.content,page,model)
                if page in book.get('reverse_unverified_pages',[]):
                    # Search-engine matches are only leads, never proof of a
                    # model, edition or photo. Verify source article firsthand.
                    reverse_heading=' '.join(h.get_text(' ',strip=True)
                        for h in BeautifulSoup(response.content,'html.parser').select('h1,title'))
                    if not (PUBLIC_STRONG_MODEL[model].search(reverse_heading)
                            and _work_token_matched_in_heading(
                                response.content,book.get('title'),aid,model)):
                        errors.append({'page':page,
                                       'reason':'reverse_page_model_or_work_not_proven'})
                        continue
                if book.get('census_new_work') and not _work_token_matched_in_heading(
                        response.content,book.get('title'),aid,model):
                    errors.append({'page':page,'reason':'new_work_identity_not_proven'})
                    continue
                if (urlsplit(page).hostname in RESEARCH_WORK_HOSTS or
                        urlsplit(page).hostname not in PAGE_HOSTS
                        and urlsplit(page).hostname not in X_PUBLIC_HOSTS):
                    title_line=' '.join(h.get_text(' ',strip=True)
                        for h in BeautifulSoup(response.content,'html.parser').select('h1,title'))
                    if not (PUBLIC_STRONG_MODEL[model].search(title_line)
                            and _work_token_matched_in_heading(
                                response.content,book.get('title'),aid,model)):
                        errors.append({'page':page,'reason':'research_work_identity_unverified'})
                        continue
                original_urls=list(urls)
                # An explicit login, wrong work/volume, or missing identity is
                # still a hard reject. Alternative parsers do not bypass it.
                social_proven=(urlsplit(page).hostname in X_PUBLIC_HOSTS
                               and safe_registered_public_page(page,model))
                legacy_work_proven=(bool(previous) and book.get('curated_images_only')
                                    and (social_proven or _work_token_matched_in_heading(
                                        response.content,book.get('title'),aid,model)))
                eligible=(alternative_engines
                          and (not book.get('curated_images_only') or legacy_work_proven)
                          and status in ('scoped_public_page','no_public_photos','unscoped_page_rejected')
                          and (urlsplit(page).hostname not in ('showartx.net','www.nicesss.com')
                               or status=='scoped_public_page'))
                if eligible:
                    from collector_full_compare import pagination_from_html
                    more=list(dict.fromkeys(list(more)+pagination_from_html(
                        response.content,page,book['source'])))
                    try:
                        alternative,engine_status=verified_alternative_candidates(
                            response.content,page,model,original_urls,known_work_urls,
                            trusted_registered_page=True)
                        # Spend the Chromium budget on pages where static HTML
                        # extraction is weak, not the first eight already-full
                        # pages. Reuse the actual dynamically rendered image URLs.
                        if (browser is not None and rendered_pages<render_budget
                                and rendered_work_pages<3
                                and (not alternative or not original_urls)):
                            rendered_pages+=1
                            rendered_work_pages+=1
                            rendered_raw=response.content
                            rendered,browser_status=browser.extract(page,model)
                            if browser.page is not None and browser_status not in (
                                    'not_run', 'http_401', 'http_403', 'http_429', 'http_451'):
                                try:
                                    from public_work_photo_extractor import recover_public_work_photo_urls
                                    actual_dom=browser.page.content().encode('utf-8')
                                    rendered_raw=actual_dom
                                    if urlsplit(page).hostname in X_PUBLIC_HOSTS:
                                        posted,_,_ = page_images(actual_dom,page,model)
                                        rendered=list(dict.fromkeys(rendered+posted))
                                        urls=list(dict.fromkeys(urls+posted))
                                    additional_dom,_=recover_public_work_photo_urls(
                                        actual_dom,page,model,trusted_work=True)
                                    rendered=list(dict.fromkeys(rendered+additional_dom))
                                    for p in pagination_from_html(
                                            actual_dom,page,book['source']):
                                        if p not in more:
                                            more.append(p)
                                except Exception as exc:
                                    errors.append({'page':page,
                                                   'reason':'chromium_photo_dom_'+type(exc).__name__})
                            if rendered:
                                alternative,_=verified_alternative_candidates(
                                    rendered_raw,page,model,original_urls,
                                    known_work_urls,rendered=rendered,
                                    trusted_registered_page=True)
                        alt_candidate_count+=len(alternative)
                        alt_photo_urls.update(alternative)
                        urls=list(dict.fromkeys(list(urls)+alternative))
                    except (ImportError,ValueError,TypeError) as e:
                        errors.append({'page':page,'reason':'alternative_engine_'+type(e).__name__})
                for p in more:
                    if reviewed_source_only and not reviewed_direct_source(p,model):
                        continue
                    if p not in visited and p not in queue:queue.append(p)
                if status!='scoped_public_page' and not (eligible and urls):
                    errors.append({'page':page,'reason':status});continue
            except Exception as e:
                errors.append({'page':page,'reason':type(e).__name__,**public_failure(e)});continue
            for url in urls:
                if new_total>=max_new:break
                if reviewed_source_only and not reviewed_direct_media(url,page,model):
                    unreviewed_count+=1
                    continue
                candidate_count+=1
                old=historic.get((aid,url))
                if book.get('curated_images_only') and not old and url not in alt_photo_urls:
                    unreviewed_count+=1;continue
                if url in seen_urls:continue
                seen_urls.add(url);variant=bool(old and old.get('public_full_variant'))
                if old and old.get('sha256') in seen_sha and not variant:continue
                # Published source sequence positions are used only within the
                # exact same existing work. New unknown URLs append once by SHA.
                number=old.get('number') if old else None
                former=next((p for p in previous if p['number']==number),None)
                if number in occupied and not variant:continue
                if variant and former and former['sha256']!=old.get('sha256'):
                    if former.get('variant_of_sha256')==old.get('sha256'):continue
                    errors.append({'number':number,'reason':'variant_slot_identity_not_proven'});continue
                try:
                    r=client.get(url);raw=r.content;p,preview,fmt=inspect(raw)
                    quality=measured_photo_quality(raw,p)
                    if variant:
                        if p['sha256'] in seen_sha:continue
                        reference=client.get(old['url']).content
                        if hashlib.sha256(reference).hexdigest()!=old['sha256'] or not same_variant(reference,raw):
                            raise ValueError('full_variant_identity_or_visual_match_failed')
                        # Only replace the same position when a decoded
                        # visual comparison establishes better image quality.
                        # Watermark absence breaks an actual visual-quality
                        # tie ONLY when both statuses are independently verified.
                        earlier=old.get('watermark_status','unknown')
                        later=book.get('candidate_watermark_status','unknown')
                        better,evidence=preferred_pair(reference,raw,old['sha256'],earlier,later)
                        if not better:
                            errors.append({'number':number,'url':url,
                                'reason':'visual_quality_not_proven_better',
                                'visual_relation':evidence.get('relation')})
                            continue
                        p['visual_quality']=evidence
                        p['variant_of_sha256']=old['sha256']
                        p['higher_resolution_replacement']=bool(former)
                        p['higher_visual_quality_replacement']=bool(former)
                    elif old and (p['sha256']!=old.get('sha256') or p['bytes']!=old.get('bytes')):
                        if not safe_reencoded_public_preview(old,raw,fmt,p['width'],p['height'],url):
                            raise ValueError('historical_bytes_changed_outside_conservative_policy')
                        p['historical_sha256']=old['sha256'];p['public_source_reencoded']=True
                    if p['sha256'] in seen_sha:continue
                    if number is None:
                        number=next_number;next_number+=1
                    occupied.add(number);seen_sha.add(p['sha256'])
                    name=f'{number:05d}-{p["sha256"][:16]}'
                    original=f'originals/{aid}/{name}.{p.pop("extension")}'
                    thumbnail=f'previews/{aid}/{name}.webp'
                    atomic_bytes(out/original,raw);atomic_bytes(out/thumbnail,preview)
                    row={**p,'number':number,'key':original,'preview':thumbnail,
                         'preview_sha256':hashlib.sha256(preview).hexdigest(),'preview_bytes':len(preview),
                         'measured_image_quality':quality,
                         'numbering_provenance':'published_source_order' if old else 'archive_append_order_not_publisher_number'}
                    images.append(row);new_total+=1;downloaded_now+=1
                    if url in alt_photo_urls:alt_new_staged+=1
                    with journal.open('a') as log:log.write(json.dumps({'album':aid,'number':number,'source':url,'photo':row,'remote_verified':False})+'\n')
                except Exception as e:errors.append({'number':number,'url':url,'reason':type(e).__name__,**public_failure(e)})
        if images:new_albums.append({'id':aid,'title':book.get('title') or aid,'publisher':book.get('publisher'),
            'expected':None,'complete':False,'images':images})
        declared_count=next((book.get(key) for key in (
            'advertised_photos','advertised_publisher_photos','public_web_edition_photos',
            'source_claimed_total_edition_photos','expected')
            if type(book.get(key)) is int and 0<book[key]<=25000),None)
        observed_saved=len({p.get('sha256') for p in previous+images if p.get('sha256')})
        deficit=max(0,declared_count-observed_saved) if declared_count else None
        reason_counts=dict(Counter(
            (e.get('reason') or e.get('cause') or 'unknown')
            if isinstance(e,dict) else str(e)
            for e in errors))
        work_result={'id':aid,'engine':'requests_scrapy_chromium_article_photo',
                     'pages':len(visited),'chromium_pages_visited_for_work':rendered_work_pages,
                     'blocked_origin_pages_not_retried':blocked_origin_pages,
                     'source_pages_registered':
                         len(set([book['source']]+book.get('source_pages',[]))),
                     'verified_official_unique_urls_staged':known_official_saved,
                     'published_image_candidates':candidate_count,
                     'individual_files_saved':len(images),
                     'alternative_engine_url_candidates':alt_candidate_count,
                     'new_staged_files_from_alternative_engines':alt_new_staged,
                     'unreviewed_legacy_image_candidates_skipped':unreviewed_count,
                     'saved_distinct_sha_after_staging':observed_saved,
                     'declared_photo_total_not_download_proof':declared_count,
                     'unfilled_declared_count_not_verified_missing':deficit,
                     'failure_categories':reason_counts,
                     'failures':errors,'cloud_readback_pass':0,'gallery_open_pass':0}
        results.append(work_result)
        print('DIRECT_WORK_SOURCE_EVIDENCE',model,aid,json.dumps({
            k:v for k,v in work_result.items() if k not in ('failures','engine')
        },ensure_ascii=False),flush=True)
        print('DIRECT_INDIVIDUAL_PHOTO_COLLECTION',model,aid,'saved',len(images),'failures',len(errors),flush=True)
    if browser is not None:browser.close()
    catalog={'schema_version':1,'model':model,'storage':'owner-private-terabox-sha-verified-bytes','albums':new_albums}
    metadata=out/'metadata';metadata.mkdir(parents=True,exist_ok=True)
    (metadata/'catalog.json').write_text(json.dumps(catalog,ensure_ascii=False,indent=2)+'\n')
    report={'model':model,'generated_at':datetime.now(timezone.utc).isoformat(),'new_local_individual_files':new_total,
            'downloaded_new_this_invocation':downloaded_now,'resumed_verified_staged_files':new_total-downloaded_now,
            'new_photo_positions':sum(not p.get('higher_resolution_replacement') for a in new_albums for p in a['images']),
            'higher_resolution_replacements':sum(bool(p.get('higher_resolution_replacement')) for a in new_albums for p in a['images']),
            'remote_verified_files':0,'gallery_open_verified_files':0,'photo_bundles_created':0,
            'owner_census_source_coverage':source_scope,
            'alternative_engines_enabled':bool(alternative_engines),
            'chromium_page_visits':rendered_pages,
            'alternative_candidate_url_groups':sum(r.get('alternative_engine_url_candidates',0) for r in results),
            'alternative_staged_new_files':sum(r.get('new_staged_files_from_alternative_engines',0) for r in results),
            'alternative_engine_page_errors':sum(
                str(error.get('reason','')).startswith('alternative_engine_')
                for r in results for error in r.get('failures',[]) if isinstance(error,dict)),
            'results':results}
    (metadata/'collection-audit.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    # Record Hydrus-inspired SHA/visual duplicate candidates from actual bytes.
    # This never changes the catalogue or blocks safe original-file publication.
    try:
        from perceptual_duplicate_audit import scan_stage
        evidence=scan_stage(out)
        (metadata/'perceptual-duplicate-evidence.json').write_text(
            json.dumps(evidence,ensure_ascii=False,indent=2)+'\n')
        print('STAGED_VISUAL_DUPLICATE_EVIDENCE',model,
              evidence['files_scanned'],'candidates',len(evidence['review_pairs']),flush=True)
    except (ValueError,OSError) as exc:
        print('STAGED_VISUAL_DUPLICATE_AUDIT_UNAVAILABLE',type(exc).__name__,flush=True)
    return report


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--root',type=Path,default=ROOT);p.add_argument('--model',choices=['mimmi','yui'],required=True);p.add_argument('--owner',type=Path,required=True);p.add_argument('--out',type=Path,required=True);p.add_argument('--max-new',type=int,default=180);p.add_argument('--max-pages',type=int,default=24);p.add_argument('--focused-only',action='store_true');p.add_argument('--album-id',action='append',default=[]);p.add_argument('--page-cycle',type=int,default=0);p.add_argument('--alternative-engines',action='store_true');p.add_argument('--render-budget',type=int,default=8);p.add_argument('--reverse-evidence',type=Path);p.add_argument('--reviewed-source-only',action='store_true');a=p.parse_args()
    if not 1<=a.max_new<=500 or not 1<=a.max_pages<=60:raise SystemExit('Bounded collection budget required')
    report=collect(a.root,a.model,json.loads(a.owner.read_text()),a.out,a.max_new,a.max_pages,focused_only=a.focused_only,album_ids=a.album_id,page_cycle=a.page_cycle,alternative_engines=a.alternative_engines,render_budget=a.render_budget,reverse_evidence=a.reverse_evidence,reviewed_source_only=a.reviewed_source_only)
    print('DIRECT_FILE_COLLECTION_COMPLETE',report['model'],report['new_local_individual_files'],'REMOTE_VERIFIED',0,'GALLERY_VERIFIED',0)
