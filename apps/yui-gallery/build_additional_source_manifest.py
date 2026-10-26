"""Register newly acquired physical files as source links, never public mirrors."""
import argparse,hashlib,json,re
from datetime import datetime,timezone
from pathlib import Path
from urllib.parse import urlsplit
from PIL import Image

ALLOWED=re.compile(r'^(?:(?:wes|bis)\.misskon\.com|lux\.mrcong\.com|(?:imgx\d{3}|images\d{2})\.pixibb\.com|s\.wujituku\.com|lh\d\.ggpht\.com)$')
def build(folders,out):
    albums=[]
    for folder in folders:
        m=json.loads((folder/'manifest.json').read_text());images=[];seen=set()
        for p in m['images']:
            u=urlsplit(p['url'])
            if u.scheme!='https' or not ALLOWED.fullmatch(u.hostname or ''):raise ValueError('Unapproved image URL')
            f=(folder/p['file']).resolve()
            if not f.is_relative_to(folder.resolve()):raise ValueError('Unsafe file path')
            raw=f.read_bytes();digest=hashlib.sha256(raw).hexdigest()
            if len(raw)!=p['bytes'] or digest!=p['sha256'] or digest in seen:raise ValueError('File integrity/duplicate error')
            with Image.open(f) as im:im.verify()
            with Image.open(f) as im:
                im.load();w,h=im.size
                if (w,h)!=(p['width'],p['height']):raise ValueError('Dimension mismatch')
            seen.add(digest);images.append({k:p[k] for k in ['number','url','sha256','bytes','width','height']})
        albums.append({'id':m['id'],'title':m['title'],'expected':m['expected'],'images':images,
                       'source_pages':m.get('source_pages',[m.get('source_page','')]),
                       'quality':'AI enhanced web edition' if m.get('ai_enhanced') else 'public web resolution',
                       'status':'verified_collected_individual_files_source_hosted_online_view'})
    payload={'schema_version':1,'generated_at':datetime.now(timezone.utc).isoformat(),
             'not_private_cloud':True,'kind':'physical_files_verified_source_links_only','albums':albums}
    out.write_text(json.dumps(payload,ensure_ascii=False,indent=2)+'\n');print('ADDITIONAL_REAL_FILES_REGISTERED',sum(len(a['images']) for a in albums))
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('folders',nargs='+',type=Path);p.add_argument('--out',type=Path,default=Path(__file__).with_name('additional-source-albums.json'));a=p.parse_args();build(a.folders,a.out)
