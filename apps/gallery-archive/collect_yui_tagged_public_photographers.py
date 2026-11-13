#!/usr/bin/env python3
"""G05: archive only real public photographer originals explicitly crediting Yui.

The photographer's exact own public timeline card must mention @super_yuisan
or 심유이. No quoted/reposted photos, face recognition, guessed media URLs,
accounts, private posts, paywalls or unverified substitute image bytes.
Photos are copied to free immutable Pages only after exact SHA + PIL decode.
"""
from __future__ import annotations
import argparse
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urljoin,urlsplit,parse_qsl
from bs4 import BeautifulSoup
import hashlib,json,re,time,requests
from collect_teapawt_public import safe_media_url,download_one,get_public_page_with_retry

ROOT=Path(__file__).resolve().parents[2]
# Public credit-bearing photographer accounts observed in creator reposts.
ACCOUNTS=('chinokun_photo','Ansongraphy','Asura_Nii','haruokumura8590',
          'Tears3134','w00ng_2','garamdall','Bulldokgu')
HOST='teapawt.net'
TAG=re.compile(r'@super_yuisan\b|심유이',re.I)

def observed_photos(html, account, url):
    """Only photos in an exact author's own credited, non-quoted post."""
    soup=BeautifulSoup(html,'html.parser')
    found={}
    credited_cards=0
    for card in soup.select('.timeline-item[data-username]'):
        if card.get('data-username','').casefold()!=account.casefold():continue
        if card.select_one('.retweet-header'):continue
        # Quote text cannot qualify a photographer's own other-image post.
        credit=card.get_text(' ',strip=True)
        for quoted in card.select('.quote,.quoted-tweet,.quoted-tweet-content'):
            credit=credit.replace(quoted.get_text(' ',strip=True),'')
        if not TAG.search(credit):continue
        credited_cards+=1
        for element in card.select('img,source,a[href]'):
            if element.find_parent(class_=re.compile(r'^(?:quote|quoted-tweet|retweet-header)$')):continue
            if element.find_parent(class_='timeline-item') is not card:continue
            fields=('href',) if element.name=='a' else (
                'data-original','data-src','data-lazy-src','src','srcset','data-srcset')
            for field in fields:
                val=element.get(field)
                if not val:continue
                for part in (val.split(',') if 'srcset' in field else [val]):
                    raw=part.strip().split()[0] if part.strip() else ''
                    photo=safe_media_url(raw,url)
                    if not photo:continue
                    key=urlsplit(photo).path
                    priority={'orig':4,'large':3,'medium':2}.get(
                        dict(parse_qsl(urlsplit(photo).query)).get('name'),1)
                    if key not in found or priority>found[key][0]:found[key]=(priority,photo)
    next_url=None
    for anchor in soup.select('a[href]'):
        label=anchor.get_text(' ',strip=True).casefold()
        if not ('load more' in label or label in ('older','next','more')):continue
        possible=urljoin(url,anchor.get('href',''))
        parsed=urlsplit(possible)
        if (parsed.scheme=='https' and parsed.hostname==HOST
            and parsed.path=='/'+account and parsed.port is None
            and not parsed.fragment and 'cursor' in dict(parse_qsl(parsed.query))):
            next_url=possible
            break
    return [p for _,p in found.values()],next_url,credited_cards

def acquire(root=ROOT, max_new=75, max_bytes=60_000_000, pages=2,accounts=ACCOUNTS,
            client=None, download=download_one):
    root=Path(root);base=root/'apps/yui-gallery'
    owner=json.loads((base/'owner-index.json').read_text())
    manifest_path=base/'stored-albums.json'
    manifest=json.loads(manifest_path.read_text())
    if owner.get('model')!='yui' or manifest.get('model')!='yui':
        raise ValueError('Yui source model mismatch')
    saved={p['sha256'] for a in owner['albums'] for p in a.get('images',[])}
    saved.update(p['sha256'] for a in manifest['albums'] for p in a.get('images',[]))
    byid={a['id']:a for a in manifest['albums']}
    seen_media=set()
    statistics=Counter()
    new=[];errors=[];spent=0
    session=client or requests.Session()
    headers={'User-Agent':'Mozilla/5.0 (compatible; PersonalPublicPhotoArchive/1.0)',
             'Accept':'text/html,application/xhtml+xml'}
    for account in accounts:
        if account not in ACCOUNTS:raise ValueError('Unregistered public photographer')
        base_url='https://teapawt.net/'+account
        next_url=base_url;visited=set()
        urls=[]
        while next_url and next_url not in visited and len(visited)<pages:
            visited.add(next_url)
            try:
                reply=get_public_page_with_retry(session,next_url,headers,attempts=2)
                if (reply.status_code!=200 or
                    urlsplit(reply.url).hostname!=HOST or
                    'html' not in reply.headers.get('Content-Type','').lower() or
                    len(reply.content)>3_000_000):raise ValueError('Photographer public HTML unavailable')
                matches,next_url,cards=observed_photos(reply.text,account,next_url)
                statistics['credited_cards']+=cards
                for url in matches:
                    if urlsplit(url).path not in seen_media:
                        seen_media.add(urlsplit(url).path);urls.append(url)
                statistics['pages_read']+=1
                if len(urls)>=30:break
                time.sleep(.2)
            except (requests.RequestException,ValueError) as exc:
                statistics['source_page_failures']+=1
                if len(errors)<15:errors.append({'account':account,'kind':type(exc).__name__})
                break
        for url in urls[:30]:
            if len(new)>=max_new or spent>=max_bytes:break
            data,error=download(url,{'url':base_url})
            statistics['attempted_media']+=1
            if data is None:
                statistics['download_failures']+=1
                if len(errors)<15:errors.append({'account':account,'kind':str(error)[:60]})
                continue
            sha=data['sha256'];raw=data['bytes']
            if sha in saved:
                statistics['already_saved_sha']+=1;continue
            if min(data['width'],data['height'])<700 or max(data['width'],data['height'])<1000:
                statistics['poor_resolution_skipped']+=1;continue
            if spent+len(raw)>max_bytes:
                statistics['budget_skipped']+=1;continue
            album_id='yui-event-'+account.lower().replace('_','-')
            album=byid.get(album_id)
            if album is None:
                album={'id':album_id,'title':'심유이 — '+account+' 공개 행사 사진',
                       'source':base_url,'publisher':'사진가 '+account,
                       'status':'individually_verified_public_photographer_photo',
                       'images':[]}
                byid[album_id]=album
            number=max([p['number'] for p in album['images']]+[0])+1
            rel='stored-albums/'+album_id+'/'+sha[:20]+'.'+data['extension']
            destination=(base/rel).resolve()
            if not destination.is_relative_to(base.resolve()):raise ValueError('Unexpected path')
            if destination.exists():
                if destination.read_bytes()!=raw:raise ValueError('Immutable file collision')
            else:
                destination.parent.mkdir(parents=True,exist_ok=True)
                destination.write_bytes(raw)
            album['images'].append({
                'number':number,'url':rel,'sha256':sha,'bytes':len(raw),
                'width':data['width'],'height':data['height'],
                'origin_page':base_url,'source_url':url,
                'quality':'photographer_public_first_party_media_not_publisher_master',
                'numbering_provenance':'new_saved_order_not_official_photo_number'})
            new.append({'album':album_id,'sha256':sha,'bytes':len(raw),'url':rel})
            saved.add(sha);spent+=len(raw);statistics['new_real_bytes']+=len(raw)
    if new:
        manifest['albums']=list(byid.values())
        manifest['physical_verified_image_count']=sum(len(a['images']) for a in manifest['albums'])
        manifest['updated']=datetime.now(timezone.utc).isoformat()
        manifest_path.write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n')
    report={'model':'yui','scope':'public_credited_photographer_photos_not_publisher_master',
            'sources':list(accounts),'new_sha':len(new),'new_bytes':spent,
            'statistics':dict(statistics),'photos':new,'errors':errors}
    (root/'.gallery-g05-tagged-photographer-report.json').write_text(
        json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    print('G05_TAGGED_PHOTOGRAPHER_ACTUAL_PHYSICAL_SOURCE_RESULT',
          json.dumps(report,ensure_ascii=False),flush=True)
    return report

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--root',type=Path,default=ROOT)
    parser.add_argument('--max-new',type=int,default=75)
    parser.add_argument('--max-bytes',type=int,default=60_000_000)
    parser.add_argument('--pages',type=int,default=2)
    args=parser.parse_args()
    if not 1<=args.max_new<=90 or not 1_000_000<=args.max_bytes<=90_000_000 or not 1<=args.pages<=3:
        raise ValueError('Unbounded public photo request')
    acquire(args.root,args.max_new,args.max_bytes,args.pages)

if __name__=='__main__':main()
