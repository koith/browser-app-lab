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
from urllib.parse import urljoin,urlsplit
from urllib.robotparser import RobotFileParser
import requests
from PIL import Image

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


def discover(target,client,cache):
    origin=target['url'];kind=target['adapter'];expected=target['expected'];selected={};seen=set();queue=[origin]
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
                match=re.fullmatch(r'https://lh\d\.ggpht\.com/[^"<> ]+/s0-e7/[^/]*Yui[^/]*-(\d{3})\.(webp|jpg)',absolute,re.I)
                if match:selected[int(match.group(1))]=absolute
            elif kind=='junmeitu':
                # The current photo is scoped to .pictures, excluding related thumbnails.
                pass
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
