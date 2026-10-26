#!/usr/bin/env python3
"""Personal gallery archival engine.

Discovers public, visible image resources with real-browser scroll and page turns,
downloads only sources listed in source_targets.json, and records provenance.
Does not log in, evade access controls, or discover paid archive URLs.
"""
from __future__ import annotations
import argparse, asyncio, hashlib, io, json, os, re, time, urllib.parse, zipfile
from collections import deque
from pathlib import Path
from datetime import datetime, timezone
import requests
from PIL import Image
from playwright.async_api import async_playwright

MAX_BYTES = 32_000_000
IMAGE_EXT = re.compile(r"\.(?:jpe?g|png|webp|avif|gif|bmp)(?:$|[?#])", re.I)
EXCLUDE_IMAGE = re.compile(r"avatar|logo|favicon|placeholder|sprite|emoji|icon|badge|default-|loading|payment|qr[.-]|vip-|thumbnail\.svg", re.I)
DATE_FMT = "%Y-%m-%dT%H:%M:%SZ"
DOM_COLLECT = r"""() => {
  const roots=[...document.querySelectorAll('article .entry-content,article .post-content,article .article-content,article .content,article,main .entry-content,main .article-content,main, #content')];
  let root=roots.find(r=>r.querySelectorAll('img').length>=2)||document.body;
  const disallow=/related|recommend|sidebar|footer|header|comment|widget|avatar|author|advert|suggested|navigation/i;
  const imgs=[];
  for(const im of root.querySelectorAll('img, picture source')){
    if(im.closest('.related,.recommended,.sidebar,.widget,.footer,.comments,.comment-list,.ad,.ads'))continue;
    if([...im.parentElement?.classList||[]].some(x=>disallow.test(x)))continue;
    const attrs=['data-original','data-full','data-zoom-image','data-lazy-src','data-src','data-url','src','currentSrc','srcset','data-srcset'];
    for(const a of attrs){
      let v=a==='currentSrc'?im.currentSrc:im.getAttribute(a);
      if(v&&v.trim())imgs.push({v,attr:a,alt:im.getAttribute('alt')||''});
    }
    const anc=im.closest('a[href]');
    if(anc)imgs.push({v:anc.href,attr:'image-link',alt:im.getAttribute('alt')||''});
  }
  const links=[];
  const here=new URL(location.href);
  for(const a of document.querySelectorAll('a[href]')){
    let u;try{u=new URL(a.href)}catch{continue}
    if(u.host!==here.host)continue;
    const txt=(a.textContent||'').trim().slice(0,40);
    const rel=a.getAttribute('rel')||'';
    if(/next|下一页|下页|后页|次へ|다음|›|»|^>\s*$|^\d{1,3}$|^(last|末页)$/i.test(txt) || /next/i.test(rel) ||
       (u.pathname===here.pathname && (u.searchParams.has('page')||u.searchParams.has('paged'))) ||
       (/\/page\/\d+\/?$/.test(u.pathname) && here.pathname.replace(/\/page\/\d+\/?$/, '/')===u.pathname.replace(/\/page\/\d+\/?$/, '/'))){
       links.push({url:u.href,text:txt,rel});
    }
  }
  return {imgs,links,documentHeight:document.documentElement.scrollHeight,scrollY:scrollY,viewportHeight:innerHeight,title:document.title,
    bodyText:(root.innerText||'').slice(0,1200)};
}"""
SCROLL_JS = r"""() => {
  const d=document.documentElement;
  window.scrollBy(0,Math.max(650,Math.floor(innerHeight*0.8)));
  let moved=0;
  for(const e of document.querySelectorAll('[style*="overflow"],.scroll-area,.scroll-container')){
    if(e.scrollHeight>e.clientHeight+300){
      const old=e.scrollTop;e.scrollTop=Math.min(e.scrollTop+Math.max(500,e.clientHeight*.8),e.scrollHeight);
      if(e.scrollTop!==old)moved++;
    }
  }
  return {scrollY,atBottom:scrollY+innerHeight>=d.scrollHeight-4,height:d.scrollHeight,moved};
}"""

def utcnow():
    return datetime.now(timezone.utc).strftime(DATE_FMT)

def canonical(url: str) -> str:
    p=urllib.parse.urlsplit(url)
    # Remove image transformation parameters only for identity comparisons.
    q=urllib.parse.parse_qsl(p.query,keep_blank_values=True)
    q=[(k,v) for k,v in q if k not in {'w','h','fit','fm','ixlib','wpsize','s','resize'}]
    return urllib.parse.urlunsplit((p.scheme.lower(),p.netloc.lower(),p.path,urllib.parse.urlencode(q),''))

def candidates(raw:str,base:str):
    raw=raw.strip()
    if raw.startswith('data:') or raw.startswith('blob:') or raw.startswith('javascript:'):
        return []
    if ',' in raw and (re.search(r'\s\d+(?:w|x)(?:,|$)',raw) or 'http' in raw):
        pairs=[]
        for p in raw.split(','):
            parts=p.strip().rsplit(' ',1)
            if not parts:continue
            weight=0
            if len(parts)==2:
                try:weight=int(parts[1].rstrip('w'))
                except ValueError:
                    try:weight=int(float(parts[1].rstrip('x'))*1000)
                    except ValueError:pass
            pairs.append((weight,parts[0]))
        return [urllib.parse.urljoin(base,x[1]) for x in sorted(pairs,reverse=True)]
    return [urllib.parse.urljoin(base,raw)]

def image_allowed(url,allowed_hosts):
    p=urllib.parse.urlsplit(url)
    if p.scheme not in ('http','https'):return False
    host=(p.hostname or '').lower()
    if not any(host==d or host.endswith('.'+d) for d in allowed_hosts):return False
    if EXCLUDE_IMAGE.search(p.path):return False
    return bool(IMAGE_EXT.search(p.path))

def image_choice(items,base,allowed_hosts):
    got={}
    # Explicit high-resolution data-original comes before display src, but same photo variants remain recorded.
    weights={'data-original':9,'data-full':9,'data-zoom-image':8,'image-link':8,'data-srcset':7,'srcset':7,'data-lazy-src':6,'data-src':6,'currentSrc':4,'src':3,'data-url':3}
    for it in items:
        for u in candidates(it['v'],base):
            if not image_allowed(u,allowed_hosts):continue
            key=canonical(u)
            entry={'url':u,'origin_page':base,'source_attribute':it['attr'],'alt':it.get('alt',''),'priority':weights.get(it['attr'],1)}
            if key not in got or entry['priority']>got[key]['priority']:
                got[key]=entry
    return got

def next_pages(links,original,visited):
    o=urllib.parse.urlsplit(original)
    result=[]
    for e in links:
        u=urllib.parse.urlsplit(e['url'])
        if u.hostname!=o.hostname or e['url'] in visited:continue
        # Strictly constrain to the current album/collection path and numbered page aliases.
        a=o.path.rstrip('/');b=u.path.rstrip('/')
        if a==b or b.startswith(a+'/page/') or a.startswith(b+'/page/'):
            page=urllib.parse.parse_qs(u.query)
            if page.get('page')==['1'] and 'next' not in e['rel']:continue
            result.append(e['url'])
    return list(dict.fromkeys(result))

async def inspect_page(page, url, allowed_hosts, max_steps=55):
    await page.goto(url,wait_until='domcontentloaded',timeout=35000)
    await page.wait_for_timeout(550)
    found={};pagination=[];stable=0;prev=(-1,-1,-1);snap=None
    for step in range(max_steps):
        snap=await page.evaluate(DOM_COLLECT)
        found.update(image_choice(snap['imgs'],page.url,allowed_hosts))
        pagination+=snap['links']
        metrics=(len(found),snap['documentHeight'],len(pagination))
        movement=await page.evaluate(SCROLL_JS)
        if metrics==prev and movement['atBottom'] and not movement['moved']:stable+=1
        else:stable=0
        prev=metrics
        if stable>=4:break
        await page.wait_for_timeout(280)
    return {'url':page.url,'title':snap['title'],'images':list(found.values()),'page_links':pagination,
            'scroll_steps':step+1,'scrolled_to_end':stable>=4,'excerpt':snap['bodyText']}

async def discover(sources, output:Path, max_pages_override=None):
    result=[]
    async with async_playwright() as p:
        browser=await p.chromium.launch(headless=True)
        context=await browser.new_context(viewport={'width':1280,'height':800},service_workers='block')
        for src in sources:
            site=src['id']; seen={}; visited=set(); queue=deque([src['url']])
            pages=[];errors=[];limit=int(max_pages_override or src.get('max_pages',12))
            page=await context.new_page()
            while queue and len(visited)<limit:
                url=queue.popleft()
                if url in visited:continue
                visited.add(url)
                try:
                    data=await inspect_page(page,url,src['image_hosts'],src.get('scroll_limit',55))
                    pages.append({k:data[k] for k in ('url','title','scroll_steps','scrolled_to_end')})
                    for im in data['images']:
                        key=canonical(im['url'])
                        if key not in seen:seen[key]=im
                    for next_url in next_pages(data['page_links'],src['url'],visited):
                        if next_url not in queue:queue.append(next_url)
                except Exception as e:
                    errors.append({'page':url,'error':type(e).__name__+': '+str(e)[:250]})
                await page.wait_for_timeout(500)
            await page.close()
            row={'id':site,'source_url':src['url'],'declared_photos':src.get('declared_photos'),
                'pages_visited':pages,'urls_discovered':list(seen.values()),'images_discovered':len(seen),
                'errors':errors,'truncated':bool(queue),'collected_at':utcnow()}
            result.append(row)
            print('DISCOVERY',site,'pages',len(pages),'urls',len(seen),'errors',len(errors),'truncated',bool(queue),flush=True)
        await browser.close()
    output.write_text(json.dumps({'generated_at':utcnow(),'sources':result},ensure_ascii=False,indent=2),encoding='utf-8')
    return result

def download(manifest:Path, dest:Path, max_images=150):
    data=json.loads(manifest.read_text(encoding='utf-8'));dest.mkdir(parents=True,exist_ok=True)
    session=requests.Session();known={};totals={}
    for source in data['sources']:
        folder=dest/source['id'];folder.mkdir(exist_ok=True)
        images=source['urls_discovered'][:max_images];done=[];errors=[]
        for i,item in enumerate(images,1):
            url=item['url'];key=canonical(url)
            try:
                if key in known:
                    item['duplicate_url_of']=known[key];continue
                resp=session.get(url,timeout=(12,28),headers={'User-Agent':'Mozilla/5.0','Referer':item['origin_page']},stream=True)
                resp.raise_for_status()
                buf=io.BytesIO()
                for chunk in resp.iter_content(65536):
                    buf.write(chunk)
                    if buf.tell()>MAX_BYTES:raise ValueError('image exceeds maximum file size')
                raw=buf.getvalue()
                if not raw:raise ValueError('empty image')
                im=Image.open(io.BytesIO(raw)); im.verify()
                im=Image.open(io.BytesIO(raw));im.load()
                if im.width<160 or im.height<160:raise ValueError('below 160px image size')
                ext={'JPEG':'jpg','PNG':'png','WEBP':'webp','GIF':'gif','AVIF':'avif'}.get(im.format)
                if not ext:raise ValueError('unrecognized format '+str(im.format))
                sha=hashlib.sha256(raw).hexdigest()
                file=folder/('%04d_%s.%s'%(i,sha[:12],ext))
                file.write_bytes(raw)
                row={**item,'local_path':str(file.relative_to(dest)),'bytes':len(raw),
                     'sha256':sha,'width':im.width,'height':im.height,'verified_at':utcnow(),'status':'downloaded'}
                done.append(row);known[key]=row['local_path']
            except Exception as ex:
                errors.append({**item,'error':str(ex)[:220]})
            time.sleep(.12)
        declared=source.get('declared_photos')
        totals[source['id']]={'discovered':source['images_discovered'],'downloaded':len(done),
            'download_failures':len(errors),'declared_photos':declared,
            'status':'partial' if errors or (declared and len(done)<declared) or source.get('truncated') else 'unverified_completeness'}
        (folder/'manifest.json').write_text(json.dumps({'source':source['source_url'],'pages':source['pages_visited'],
            'downloaded':done,'failed':errors,'summary':totals[source['id']]},ensure_ascii=False,indent=2),encoding='utf-8')
    (dest/'summary.json').write_text(json.dumps(totals,ensure_ascii=False,indent=2),encoding='utf-8')
    with zipfile.ZipFile('yui-public-archive-dynamic.zip','w',zipfile.ZIP_DEFLATED,compresslevel=4) as zipf:
        for file in dest.rglob('*'):
            if file.is_file():zipf.write(file,file.relative_to(dest))
    with zipfile.ZipFile('yui-public-archive-dynamic.zip') as zipf:
        assert zipf.testzip() is None
    print('DOWNLOAD_SUMMARY',json.dumps(totals,ensure_ascii=False),flush=True)
    return totals

def main():
    a=argparse.ArgumentParser()
    a.add_argument('--targets',default='apps/yui-gallery/source_targets.json')
    a.add_argument('--discover-only',action='store_true')
    a.add_argument('--max-pages',type=int,default=None)
    a.add_argument('--max-images',type=int,default=150)
    a.add_argument('--output',default='yui-dynamic-discovery.json')
    ns=a.parse_args()
    sources=json.loads(Path(ns.targets).read_text(encoding='utf-8'))['sources']
    out=Path(ns.output)
    asyncio.run(discover(sources,out,ns.max_pages))
    if not ns.discover_only:download(out,Path('yui-dynamic-images'),ns.max_images)
if __name__=='__main__':
    main()
