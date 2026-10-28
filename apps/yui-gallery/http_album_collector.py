#!/usr/bin/env python3
"""Free, resumable public-HTML album adapters; unchanged individual files only.

Follow observed album pagination, never enumerate CDN paths or bypass blocks.
Outputs must be outside the public repository. Publish only source URL metadata.
"""
import argparse,hashlib,io,json,re,time,threading
from concurrent.futures import ThreadPoolExecutor,as_completed
from datetime import datetime,timezone
from html import unescape
from pathlib import Path
from urllib.parse import urljoin,urlsplit,parse_qs
from urllib.robotparser import RobotFileParser
import requests
from PIL import Image
from bs4 import BeautifulSoup

AGENT='YuiPersonalArchive/0.1 (+https://github.com/koith/browser-app-lab)'


def links(html):return [unescape(x) for x in re.findall(r'(?:href|src|data-src)=["\x27]([^"\x27]+)',html)]

class PublicPages:
    def __init__(self):self.session=requests.Session();self.robots={};self.last={}
    def get(self,url):
        host=urlsplit(url).netloc
        if host not in self.robots:
            robot=RobotFileParser();r=self.session.get('https://'+host+'/robots.txt',timeout=20)
            if r.status_code in (401,403):raise ValueError('robots.txt denies access: '+host)
            if r.status_code>=500:raise ValueError('robots.txt unavailable: '+host)
            robot.parse(r.text.splitlines() if r.ok else []);self.robots[host]=robot
        if not self.robots[host].can_fetch(AGENT,url):raise ValueError('Disallowed by robots.txt: '+url)
        time.sleep(max(0,0.6-(time.monotonic()-self.last.get(host,0))))
        r=self.session.get(url,timeout=(15,40),headers={'User-Agent':AGENT})
        self.last[host]=time.monotonic();r.raise_for_status()
        if urlsplit(r.url).hostname!=urlsplit(url).hostname:raise ValueError('Unexpected redirect host')
        return r.text


def fourkup_individual_links(html, origin, target):
    """Only body-scoped, explicitly published original-size links and sibling parts."""
    soup=BeautifulSoup(html,'html.parser');heading=soup.select_one('h1');body=soup.select_one('.entry-content')
    title=heading.get_text(' ',strip=True) if heading else ''
    if not body or not re.search(r'\bYui\b',title,re.I) or 'SWEETBOX' not in title.upper():
        raise ValueError('4kup requested model/publisher body not confirmed')
    observed=[urljoin(origin,u) for u in links(str(body))]
    if re.search(r'AI[\s_-]*Enhanced',title+' '+' '.join(observed),re.I) and not target.get('ai_enhanced'):
        raise ValueError('Source declares AI-enhanced; keep a separately labelled edition')
    images={}
    for url in observed:
        parsed=urlsplit(url)
        old=re.fullmatch(r'lh\d\.ggpht\.com',parsed.hostname or '') and '/s0-e7/' in parsed.path
        new=parsed.hostname=='blogger.googleusercontent.com' and re.search(r'/(?:s0|s0-e7)/',parsed.path)
        number=re.search(r'Yui[^/]*-(\d{3})\.(?:webp|jpg)$',parsed.path,re.I)
        if parsed.scheme!='https' or parsed.username or parsed.password or not (old or new) or not number:continue
        n=int(number.group(1))
        if 1<=n<=target['expected']:
            if n in images and images[n]!=url:raise ValueError('Ambiguous full-size photo number')
            images[n]=url
    if not images:raise ValueError('Only preview-sized photos; no published full-size individual links')
    base=re.sub(r'-part\d+/$', '-part',origin)
    parts=[]
    if base!=origin:
        for a in soup.select('a[href]'):
            url=urljoin(origin,a['href'])
            if re.fullmatch(re.escape(base)+r'\d+/',url):parts.append(url)
    return images,parts

def discover(target,client,cache):
    origin=target['url'];kind=target['adapter'];expected=target['expected'];selected={};seen=set();queue=[origin];image_order={}
    parsed=urlsplit(origin)
    if kind=='junmeitu':stem=re.sub(r'-\d+(?=\.html$)','',parsed.path)[:-5]
    while queue:
        url=queue.pop(0)
        if url in seen:continue
        if len(seen)>=500:raise ValueError('Public pagination budget exceeded')
        cached=cache/(hashlib.sha256(url.encode()).hexdigest()[:16]+'.html')
        html=cached.read_text() if cached.is_file() else client.get(url);seen.add(url)
        (cache/(hashlib.sha256(url.encode()).hexdigest()[:16]+'.html')).write_text(html)
        for raw in links(html):
            absolute=urljoin(url,raw);u=urlsplit(absolute)
            if kind=='misskon':
                match=re.fullmatch(r'https://(?:(?:wes|bis)\.misskon\.com|lux\.mrcong\.com)/images/[^"<> ]+Yui[^"<> ]+-(\d{3})[a-f0-9]*\.(webp|jpg)',absolute,re.I)
                if match:selected[int(match.group(1))]=absolute
                if re.fullmatch(re.escape(origin)+r'\d+/',absolute) and absolute not in seen:queue.append(absolute)
            elif kind=='4kup':
                pass
            elif kind=='kaizty':
                heading=re.search(r'<title>(.*?)</title>',html,re.S)
                terms=target.get('identity_terms',['Yui','Seethrough'])
                if not heading or any(term.casefold() not in unescape(heading.group(1)).casefold() for term in terms):raise ValueError('Kaizty album identity mismatch')
                if re.fullmatch(r'https://i[012]\.wp\.com/cdn[12]\.thismore\.fun/[ds]\d/[^?<> ]+-d\.jpg',absolute):
                    # Obfuscated source names do not encode canonical photo numbers.
                    # Preserve distinct observed URLs, then visually match editions.
                    candidate=absolute
                    if target.get('image_route')=='published_direct_fallback':
                        if not re.search(r'image\.src\s*=\s*a\.replace\(',html):raise ValueError('Source does not publish a direct fallback route')
                        candidate=re.sub(r'^https://i[012]\.wp\.com/','https://',candidate)
                    if candidate not in image_order:image_order[candidate]=len(image_order)+1
                    selected[image_order[candidate]]=candidate
                query=parse_qs(u.query)
                if u.netloc==parsed.netloc and u.path==parsed.path and set(query)<={'page','m'} and all(str(v).isdigit() and 1<=int(v)<=100 for v in query.get('page',['1'])) and absolute not in seen:queue.append(absolute)
            elif kind=='junmeitu':
                # The current photo is scoped to .pictures, excluding related thumbnails.
                pass
        if kind=='4kup':
            found,parts=fourkup_individual_links(html,url,target)
            for n,u in found.items():
                if n in selected and selected[n]!=u:raise ValueError('Conflicting sibling-part image number')
                selected[n]=u
            queue.extend(u for u in parts if u not in seen and u not in queue)
        if kind=='girlatlas':
            heading=re.search(r'<h1[^>]*>(.*?)</h1>',html,re.S)
            title=unescape(re.sub(r'<[^>]+>','',heading.group(1))).strip() if heading else ''
            if ('Yui' not in title or '유이' not in title
                    or '/tag?id=68f545da0e41b873a9cfea1c' not in html):
                raise ValueError('Girl Atlas requested Korean model metadata not confirmed')
            count=re.search(r'Photos</label>.*?class="field-control"[^>]*>\s*(\d+)/(\d+)',html,re.S)
            if not count or tuple(map(int,count.groups()))!=(expected,expected):
                raise ValueError('Girl Atlas full public photo count not confirmed')
            for tag in re.findall(r'<a\b[^>]*>',html):
                if 'data-fancybox="Photo"' not in tag or 'visible="True"' not in tag:continue
                src=re.search(r'data-src="([^"]+)"',tag);number=re.search(r'index="(\d+)"',tag)
                if not src or not number:continue
                candidate=urljoin(url,unescape(src.group(1)))
                album_id=parse_qs(parsed.query).get('id',[''])[0]
                if not re.fullmatch(r'https://www\.girl-atlas\.com/static/albums/\d{4}-\d{2}-\d{2}/'+re.escape(album_id)+r'/[^/<>?]+\.(?:jpg|png|webp)!lrg',candidate):
                    raise ValueError('Unexpected public photo route')
                selected[int(number.group(1))+1]=candidate
        if kind=='junmeitu':
            number_match=re.fullmatch(re.escape(stem.removeprefix('/en'))+r'(?:-(\d+))?\.html',urlsplit(url).path.removeprefix('/en'))
            if not number_match:raise ValueError('Album page path mismatch')
            number=int(number_match.group(1) or 1)
            block=re.search(r'<div class="pictures">(.*?)</div>',html,re.S)
            photos=[x for x in links(block.group(1) if block else '') if x.startswith('https://s.wujituku.com/upload/') and 'thumb_' not in x]
            if len(photos)!=1:raise ValueError('Expected one public photo per page')
            selected[number]=photos[0]
            for raw in re.findall(r'href=["\x27]([^"\x27]+)',html):
                absolute=urljoin(url,unescape(raw));u=urlsplit(absolute)
                if u.netloc==parsed.netloc and re.fullmatch(re.escape(stem.removeprefix('/en'))+r'(?:-\d+)?\.html',u.path.removeprefix('/en')) and absolute not in seen:queue.append(absolute)
    if not selected:raise ValueError('No publicly visible individual images')
    return selected,sorted(seen)


def download(number,url,folder,old):
    if old:
        file=folder/old['file']
        if file.is_file() and hashlib.sha256(file.read_bytes()).hexdigest()==old['sha256']:return old
    with requests.get(url,stream=True,timeout=(15,50),headers={'User-Agent':AGENT},allow_redirects=False) as r:
        r.raise_for_status()
        if r.status_code!=200:raise ValueError('Expected direct photo HTTP 200')
        blob=bytearray()
        for chunk in r.iter_content(65536):
            blob.extend(chunk)
            if len(blob)>50_000_000:raise ValueError('Oversized image')
    if len(blob)<3000:raise ValueError('Tiny/non-photo response')
    with Image.open(io.BytesIO(blob)) as im:im.verify()
    with Image.open(io.BytesIO(blob)) as im:
        im.load();width,height=im.size;ext={'JPEG':'jpg','PNG':'png','WEBP':'webp','AVIF':'avif'}.get(im.format)
    if min(width,height)<300 or not ext:raise ValueError('Not a full visible web photo')
    digest=hashlib.sha256(blob).hexdigest();filename=f'{number:04d}-{digest[:12]}.{ext}'
    file=folder/filename;temp=file.with_suffix(file.suffix+'.part');temp.write_bytes(blob);temp.replace(file)
    return {'number':number,'file':filename,'url':url,'sha256':digest,'bytes':len(blob),'width':width,'height':height}


def collect(target,out):
    folder=out/target['id'];folder.mkdir(parents=True,exist_ok=True);cache=folder/'pages';cache.mkdir(exist_ok=True)
    old={}
    if (folder/'manifest.json').exists():old={p['number']:p for p in json.loads((folder/'manifest.json').read_text()).get('images',[])}
    selected,pages=discover(target,PublicPages(),cache)
    images=[];failures=[]
    with ThreadPoolExecutor(max_workers=3) as pool:
        jobs={pool.submit(download,n,url,folder,old.get(n)):n for n,url in selected.items()}
        for future in as_completed(jobs):
            try:images.append(future.result())
            except Exception as exc:failures.append({'number':jobs[future],'error':str(exc)[:180]})
    images.sort(key=lambda p:p['number'])
    unique=len({p['sha256'] for p in images})
    manifest={**target,'title':target['title'],'source_pages':pages,'images':images,'failures':failures,
              'quality':'public_web_resolution','publisher_original_verified':False,
              'checked_at':datetime.now(timezone.utc).isoformat(),'complete_sequence':{p['number'] for p in images}==set(range(1,target['expected']+1)) and unique==len(images) and not failures}
    (folder/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n')
    print('PUBLIC_HTTP_ALBUM',target['id'],len(images),'unique',unique,'expected',target['expected'],'pages',len(pages),flush=True)
    # Preserve partial real files and expose missing sequence members explicitly.
    manifest['missing_numbers']=sorted(set(range(1,target['expected']+1))-{p['number'] for p in images})
    (folder/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n')
    if images and not target.get('requires_canonical_match'):
        from build_additional_source_manifest import build
        gallery=Path(__file__).with_name('additional-source-albums.json')
        existing=json.loads(gallery.read_text())['albums'] if gallery.exists() else []
        # An alternate edition belongs to its already registered canonical work.
        if not target.get('alternate_of') or not any(a['id']==target['alternate_of'] for a in existing):
            build([folder],gallery)
    return manifest


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--targets',type=Path,required=True);parser.add_argument('--out',type=Path,required=True);args=parser.parse_args()
    if args.out.resolve().is_relative_to(Path(__file__).resolve().parents[2]):parser.error('Use a private output directory outside the public repository')
    targets=json.loads(args.targets.read_text())['sources'];report=[]
    with ThreadPoolExecutor(max_workers=3) as pool:
        jobs={pool.submit(collect,t,args.out):t for t in targets}
        for future in as_completed(jobs):
            t=jobs[future]
            try:
                m=future.result();report.append({'id':t['id'],'files':len(m['images']),'complete':m['complete_sequence'],'missing':m['missing_numbers']})
            except Exception as exc:
                report.append({'id':t['id'],'files':0,'complete':False,'error':str(exc)[:300]});print('PUBLIC_HTTP_ERROR',report[-1],flush=True)
    args.out.mkdir(parents=True,exist_ok=True);(args.out/'collection-report.json').write_text(json.dumps(report,indent=2)+'\n')
    if any(not r['complete'] for r in report):raise SystemExit(1)

if __name__=='__main__':main()
