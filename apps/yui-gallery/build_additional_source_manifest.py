"""Register newly acquired physical files as source links, never public mirrors."""
import argparse,hashlib,json,re,fcntl,os,tempfile
from datetime import datetime,timezone
from pathlib import Path
from urllib.parse import urlsplit
from PIL import Image

ALLOWED=re.compile(r'^(?:cdn\.jliji\.com|cdn\.v2ph\.com|i[012]\.wp\.com|(?:wes|bis)\.misskon\.com|lux\.mrcong\.com|(?:imgx\d{3}|images\d{2})\.pixibb\.com|s\.wujituku\.com|lh\d\.ggpht\.com)$')
def build(folders,out,replace=False):
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
        numbers=[p['number'] for p in images]
        if len(set(numbers))!=len(numbers) or any(not isinstance(n,int) or n<1 or n>m['expected'] for n in numbers):raise ValueError('Invalid or duplicate photo sequence')
        albums.append({'id':m['id'],'title':m['title'],'expected':m['expected'],'images':images,
                       'source_pages':m.get('source_pages',[m.get('source_page','')]),
                       'acquired':len(images),'complete_sequence':set(numbers)==set(range(1,m['expected']+1)),
                       'missing_numbers':sorted(set(range(1,m['expected']+1))-set(numbers)),
                       'resolution_review_required':any(max(p['width'],p['height'])<1920 for p in images),
                       'minimum_long_edge':min((max(p['width'],p['height']) for p in images),default=0),
                       'quality':'AI enhanced web edition' if m.get('ai_enhanced') else 'public web resolution',
                       'status':'verified_collected_individual_files_source_hosted_online_view'})
    # Parallel album downloads must not overwrite each other's registrations.
    with out.with_suffix('.registration.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX)
        if out.exists() and not replace:
            existing={a['id']:a for a in json.loads(out.read_text())['albums']}
            for a in albums:
                previous=existing.get(a['id'])
                if previous:
                    old={p['number']:p for p in previous['images']}
                    for photo in a['images']:
                        prior=old.get(photo['number'])
                        if prior and prior['width']*prior['height']>photo['width']*photo['height']:
                            photo.update(prior)
                    # A failed or smaller rerun cannot discard already verified files.
                    incoming={p['number']:p for p in a['images']}
                    old.update(incoming);a['images']=sorted(old.values(),key=lambda p:p['number'])
                    a['expected']=max(a['expected'],previous['expected'])
                    a['acquired']=len(a['images'])
                    a['missing_numbers']=sorted(set(range(1,a['expected']+1))-set(old))
                    a['complete_sequence']=not a['missing_numbers']
                    a['resolution_review_required']=any(max(p['width'],p['height'])<1920 for p in a['images'])
                    a['minimum_long_edge']=min(max(p['width'],p['height']) for p in a['images'])
                existing[a['id']]=a
            albums=list(existing.values())
        payload={'schema_version':1,'generated_at':datetime.now(timezone.utc).isoformat(),
                 'not_private_cloud':True,'kind':'physical_files_verified_source_links_only','albums':albums}
        fd,name=tempfile.mkstemp(dir=out.parent,prefix='.registration-',suffix='.json')
        try:
            with os.fdopen(fd,'w') as handle:json.dump(payload,handle,ensure_ascii=False,indent=2);handle.write('\n')
            os.replace(name,out)
        finally:
            if os.path.exists(name):os.unlink(name)
    print('ADDITIONAL_REAL_FILES_REGISTERED',sum(len(a['images']) for a in albums))
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('folders',nargs='+',type=Path);p.add_argument('--replace',action='store_true');p.add_argument('--out',type=Path,default=Path(__file__).with_name('additional-source-albums.json'));a=p.parse_args();build(a.folders,a.out,a.replace)
