#!/usr/bin/env python3
"""Archive creator-published public social media across paginated pages.

Follows only the normal public Next cursor visible on /super_yuisan/media.
No login, account session, DRM, paid images or access-control circumvention.
"""
from __future__ import annotations
import argparse, concurrent.futures, hashlib, io, json, re, time, zipfile
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urljoin, urlsplit, urlunsplit, parse_qs, urlencode
import requests
from bs4 import BeautifulSoup
from PIL import Image

ROOT='https://teapawt.net/super_yuisan/media'
OUTPUT=Path('yui-sns-archive')
PROFILE='super_yuisan'
MEDIA=re.compile(r'https?://pbs\.twimg\.com/media/([A-Za-z0-9_-]+)(?:\.(jpe?g|png|webp))?(?:\?[^\'"\s<>]*)?',re.I)
STATUS=re.compile(r'(?:teapawt\.net|x\.com|xitter\.cf)/super_yuisan/status/(\d+)',re.I)
HEADERS={'User-Agent':'Mozilla/5.0 (compatible; personal photo archival; +https://github.com/koith/browser-app-lab)','Accept':'text/html,application/xhtml+xml;q=0.9,*/*;q=0.8'}
ALLOWED='teapawt.net'
MIN_BYTES=9000

def normalize_photo(u):
    m=MEDIA.search(u)
    if not m: return None
    return 'https://pbs.twimg.com/media/'+m.group(1)+'.'+(m.group(2) or 'jpg').lower()+'?name=orig'

def record_page(html,url):
    soup=BeautifulSoup(html,'html.parser')
    photos={}
    def add(u,el):
        original=normalize_photo(u)
        if not original:return
        photo_id=original.split('/media/')[1].split('.')[0]
        post=''
        cur=el
        for _ in range(8):
            if not cur or not hasattr(cur,'find_all'):break
            try:
                anchors=cur.find_all('a',href=True,limit=20)
                for a in anchors:
                    m=STATUS.search(urljoin(url,a['href']))
                    if m:
                        post='https://x.com/super_yuisan/status/'+m.group(1)
                        break
            except Exception:pass
            if post:break
            cur=cur.parent
        photos[photo_id]={'id':photo_id,'url':original,'post':post,'date':'','source_page':url,'name':photo_id+'.jpg'}
    for a in soup.find_all('a',href=True):
        if 'pbs.twimg.com/media/' in a['href']:add(a['href'],a)
    for img in soup.find_all('img'):
        for attr in ('src','data-src','srcset','data-srcset'):
            value=img.get(attr,'')
            if not value:continue
            if 'pbs.twimg.com/media/' in value:
                for piece in value.split(','):
                    add(piece.strip().split(' ')[0],img)
    cursor_links=[]
    for a in soup.find_all('a',href=True):
        candidate=urljoin(url,a['href'])
        p=urlsplit(candidate)
        if p.hostname!=ALLOWED or p.path!='/super_yuisan/media':continue
        if not parse_qs(p.query).get('cursor'):continue
        if candidate != url:
            cursor_links.append(candidate)
    # Normal Teapawt appends the "Show more" cursor last. A stale previous cursor is excluded by visited set.
    return photos, list(dict.fromkeys(cursor_links)), {'title':soup.title.get_text(' ',strip=True) if soup.title else '', 'page_bytes':len(html), 'photos':len(photos)}

def crawl_pages(session,max_pages,delay):
    url=ROOT;seen=set();allphotos={};pages=[]
    for page_index in range(1,max_pages+1):
        if url in seen:break
        seen.add(url)
        try:
            resp=session.get(url,timeout=(15,30),headers=HEADERS)
            resp.raise_for_status()
            photos,nexts,meta=record_page(resp.text,url)
            added=0
            for k,im in photos.items():
                if k not in allphotos:
                    allphotos[k]=im;added+=1
                elif not allphotos[k].get('post') and im.get('post'):
                    allphotos[k]['post']=im['post']
            next_url=next((candidate for candidate in reversed(nexts) if candidate not in seen),None)
            pages.append({'index':page_index,'url':url,'found':len(photos),'new':added,'next':bool(next_url),'response_bytes':meta['page_bytes']})
            print('SNS_PAGE',page_index,'found',len(photos),'new',added,'overall',len(allphotos),'next',bool(next_url),flush=True)
            if not next_url or (not added and page_index>2):
                break
            url=next_url
            time.sleep(delay)
        except Exception as e:
            pages.append({'index':page_index,'url':url,'error':str(e)[:220]})
            print('SNS_PAGE_ERROR',page_index,type(e).__name__,str(e)[:180],flush=True)
            break
    return list(allphotos.values()),pages

def download_image(item,session):
    original=item['url']
    for n in range(3):
        try:
            resp=session.get(original,headers={'User-Agent':'Mozilla/5.0','Accept':'image/*'},timeout=(15,35))
            resp.raise_for_status()
            if len(resp.content)>24_000_000:raise ValueError('Image >24MB')
            raw=resp.content
            if len(raw)<MIN_BYTES:raise ValueError('Too few image bytes')
            with Image.open(io.BytesIO(raw)) as img:
                img.verify()
            with Image.open(io.BytesIO(raw)) as img:
                fmt=img.format;w,h=img.size
            if min(w,h)<250:raise ValueError('Too small')
            extension={'JPEG':'jpg','PNG':'png','WEBP':'webp'}.get(fmt)
            if extension is None:raise ValueError('Unknown image format '+str(fmt))
            return {**item,'status':'ok','width':w,'height':h,'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest(),'extension':extension},raw
        except Exception as e:
            error=str(e)
            if n<2:time.sleep((n+1)*.8)
    return {**item,'status':'error','error':error[:240]},None

def save_archive(photos,pages,workers,part_size):
    OUTPUT.mkdir(exist_ok=True)
    session=requests.Session()
    session.headers.update({'User-Agent':'Mozilla/5.0'})
    downloaded=[]
    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as pool:
        futures={pool.submit(download_image,p,session):i for i,p in enumerate(photos)}
        result={}
        for f in concurrent.futures.as_completed(futures):
            i=futures[f]
            try:result[i]=f.result()
            except Exception as e:result[i]=({**photos[i],'status':'error','error':str(e)},None)
            if len(result)%25==0:print('SNS_DOWNLOAD_PROGRESS',len(result),'/',len(photos),flush=True)
    chunks=[];part=[];digest_to_file={}
    for i in sorted(result):
        row,raw=result[i]
        if raw:
            filename='images/%04d_%s.%s'%(i+1,row['id'],row['extension'])
            row['filename']=filename
            if row['sha256'] in digest_to_file:
                row['status']='duplicate';row['duplicate_of']=digest_to_file[row['sha256']]
            else:
                digest_to_file[row['sha256']]=filename
                part.append((filename,raw))
        downloaded.append(row)
        if len(part)>=part_size:
            chunks.append(part);part=[]
    if part:chunks.append(part)
    if not chunks:raise RuntimeError('No images successfully downloaded; refusing empty archive.')
    for n,chunk in enumerate(chunks,1):
        zip_path=OUTPUT/('Yui_SNS_%03d.zip'%n)
        with zipfile.ZipFile(zip_path,'w',zipfile.ZIP_DEFLATED,compresslevel=4) as z:
            for filename,data in chunk:z.writestr(filename,data)
            z.writestr('ABOUT.txt','Personal archive of publicly displayed posts from @super_yuisan; original photographs remain credited to their authors.\n')
        with zipfile.ZipFile(zip_path) as z:
            bad=z.testzip()
            if bad is not None:raise RuntimeError('Zip CRC invalid: '+bad)
        print('SNS_ARCHIVE_PART',n,'files',len(chunk),'size',zip_path.stat().st_size,flush=True)
    report={'generated':datetime.now(timezone.utc).isoformat(),'source':ROOT,'pages':pages,
            'total_discovered':len(photos),'actual_downloaded':sum(x['status']=='ok' for x in downloaded),
            'duplicates':sum(x['status']=='duplicate' for x in downloaded),
            'failures':sum(x['status']=='error' for x in downloaded),
            'archive_parts':len(chunks),'items':downloaded}
    (OUTPUT/'manifest.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    (OUTPUT/'summary.json').write_text(json.dumps({k:v for k,v in report.items() if k!='items'},ensure_ascii=False,indent=2),encoding='utf-8')
    (OUTPUT/'feed.json').write_text(json.dumps({'updated':report['generated'],'source':ROOT,
        'images':[{'url':p['url'],'post':p.get('post',''),'date':p.get('date',''),'name':p['name'],'caption':'심유이 공개 SNS'} for p in downloaded if p['status'] in ('ok','duplicate')]},ensure_ascii=False,indent=2),encoding='utf-8')
    print('SNS_ARCHIVE_FINAL',json.dumps({k:report[k] for k in ('total_discovered','actual_downloaded','duplicates','failures','archive_parts')},ensure_ascii=False),flush=True)

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--max-pages',type=int,default=30)
    ap.add_argument('--delay',type=float,default=.35)
    ap.add_argument('--workers',type=int,default=5)
    ap.add_argument('--part-size',type=int,default=65)
    ap.add_argument('--discover-only',action='store_true')
    args=ap.parse_args()
    session=requests.Session()
    photos,pages=crawl_pages(session,args.max_pages,args.delay)
    if not photos:raise SystemExit('No public images found. Archive not generated.')
    if args.discover_only:
        Path('yui-sns-discovery.json').write_text(json.dumps({'pages':pages,'images':photos},ensure_ascii=False,indent=2),encoding='utf-8')
        print('SNS_DISCOVERY_FINAL',len(photos),len(pages),flush=True)
    else:save_archive(photos,pages,args.workers,args.part_size)
if __name__=='__main__':main()
