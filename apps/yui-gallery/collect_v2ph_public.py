"""Read public V2PH album images, stopping at the first login restriction.

No authentication bypass. Partial public editions remain explicitly incomplete.
Use visual matching before replacing photographs from a different edition.
"""
import argparse,json,re,hashlib
from concurrent.futures import ThreadPoolExecutor
from html import unescape
from pathlib import Path
from urllib.parse import urljoin,urlsplit
from http_album_collector import PublicPages,download

def collect(target,out):
 folder=out/target['id'];folder.mkdir(parents=True,exist_ok=True)
 client=PublicPages();pending=[target['url']];seen=set();selected={};restricted=[]
 while pending:
  url=pending.pop(0)
  if url in seen:continue
  html=client.get(url);seen.add(url)
  (folder/(hashlib.sha256(url.encode()).hexdigest()[:16]+'.html')).write_text(html)
  if 'restricted-login-page' in html:restricted.append(url);break
  if not re.search(r'href="/actor/Yui(?:\?|\")',html):raise ValueError('Yui identity not confirmed')
  for tag in re.findall(r'<img\b[^>]+>',html):
   src=re.search(r'src="(https://cdn\.v2ph\.com/photos/[^"<>]+)"',tag);alt=re.search(r'alt="([^"]+)"',tag)
   if not src or not alt or 'album-photo' not in tag:continue
   n=re.search(r' (\d+)$',unescape(alt.group(1)))
   if n:selected[int(n.group(1))+1]=unescape(src.group(1))
  for raw in re.findall(r'href="([^"]+)"',html):
   u=urljoin(url,unescape(raw))
   if urlsplit(u).hostname=='www.v2ph.com' and urlsplit(u).path==urlsplit(target['url']).path and u not in seen:pending.append(u)
  if len(seen)>100:raise ValueError('Pagination budget exceeded')
 entries=[];failures=[]
 for number,url in sorted(selected.items()):
  try:entries.append(download(number,url,folder,None))
  except Exception as e:failures.append({'number':number,'error':str(e)})
 m={**target,'source_pages':sorted(seen),'images':entries,'failures':failures,'restricted_pages':restricted,'publisher_original_verified':False,'complete_sequence':set(selected)==set(range(1,target['expected']+1)) and len(entries)==target['expected']}
 (folder/'manifest.json').write_text(json.dumps(m,ensure_ascii=False,indent=2)+'\n')
 print('V2PH_PUBLIC_FILES',target['id'],len(entries),'restricted',len(restricted),flush=True);return m
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--targets',type=Path,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args()
 if a.out.resolve().is_relative_to(Path(__file__).resolve().parents[2]):p.error('Use a private output outside the repository')
 targets=json.loads(a.targets.read_text())['sources']
 with ThreadPoolExecutor(max_workers=2) as pool:rows=list(pool.map(lambda t:collect(t,a.out),targets))
 (a.out/'report.json').write_text(json.dumps([{k:v for k,v in m.items() if k!='images'} for m in rows],ensure_ascii=False,indent=2)+'\n')
