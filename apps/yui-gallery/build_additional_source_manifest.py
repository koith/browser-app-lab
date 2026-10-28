"""Register newly acquired physical files as source links, never public mirrors."""
import argparse,hashlib,json,re,fcntl,os,tempfile
from datetime import datetime,timezone
from pathlib import Path
from urllib.parse import urlsplit
from PIL import Image
from identity_policy import ensure_allowed
from photo_quality_policy import replacement_reason,watermark_review,watermark_status

ALLOWED=re.compile(r'^(?:blogger\.googleusercontent\.com|cdn\.imgcup\.com|cdn\.jliji\.com|cdn\.v2ph\.com|i[012]\.wp\.com|cdn[12]\.thismore\.fun|(?:wes|bis)\.misskon\.com|lux\.mrcong\.com|(?:imgx\d{3}|images\d{2})\.pixibb\.com|s\.wujituku\.com|lh\d\.ggpht\.com|www\.girl-atlas\.com|pbs\.twimg\.com|djawaphoto\.com|blog\.hacosta\.co\.jp|img1\.gamersky\.com|upload3\.inven\.co\.kr|pub-376e2756f81341f087a414464f9a25ec\.r2\.dev)$')
def build(folders,out,replace=False):
    albums=[]
    for folder in folders:
        m=json.loads((folder/'manifest.json').read_text());images=[];seen=set()
        ensure_allowed(m['id'],m.get('source_pages',[m.get('source_page',m.get('url',''))]),m['images'])
        for p in m['images']:
            u=urlsplit(p['url'])
            if u.scheme!='https' or u.username or u.password or not ALLOWED.fullmatch(u.hostname or ''):raise ValueError('Unapproved image URL')
            f=(folder/p['file']).resolve()
            if not f.is_relative_to(folder.resolve()):raise ValueError('Unsafe file path')
            raw=f.read_bytes();digest=hashlib.sha256(raw).hexdigest()
            if len(raw)!=p['bytes'] or digest!=p['sha256'] or digest in seen:raise ValueError('File integrity/duplicate error')
            with Image.open(f) as im:im.verify()
            with Image.open(f) as im:
                im.load();w,h=im.size
                if (w,h)!=(p['width'],p['height']):raise ValueError('Dimension mismatch')
            seen.add(digest);images.append({**{k:p[k] for k in ['number','url','sha256','bytes','width','height']},
                                           **{k:p[k] for k in ['origin_page','discovery_page','source_country','source_attribute','published_at','published_at_text','photographer_credit','sample_label','alternative_sources'] if k in p},
                                           'site_watermark_review':watermark_review(p)})
        numbers=[p['number'] for p in images]
        if len(set(numbers))!=len(numbers) or any(not isinstance(n,int) or n<1 or n>m['expected'] for n in numbers):raise ValueError('Invalid or duplicate photo sequence')
        public_subset=bool(m.get('not_complete_photobook'))
        albums.append({'id':m['id'],'title':m['title'],'expected':m['expected'],'images':images,
                       **{k:m[k] for k in ['publisher','collection_kind','not_complete_photobook','expected_total_unknown','advertised_publisher_photos','numbering_kind','source_countries'] if k in m},
                       'source_pages':m.get('source_pages',[m.get('source_page','')]),
                       'acquired':len(images),'complete_sequence':not public_subset and set(numbers)==set(range(1,m['expected']+1)),
                       'missing_numbers':None if m.get('expected_total_unknown') else sorted(set(range(1,m['expected']+1))-set(numbers)),
                       'resolution_review_required':True,
                       'highest_resolution_status':'unverified_seek_larger_or_publisher_original',
                       'publisher_original_verified':False,
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
                    if a['quality']=='AI enhanced web edition' and previous.get('quality')!='AI enhanced web edition':
                        raise ValueError('AI-enhanced copies require a separate edition ID')
                    if a.get('not_complete_photobook'):
                        if not previous.get('not_complete_photobook'):
                            raise ValueError('Public subset cannot replace a complete work')
                        # Timelines prepend new posts. Their row numbers are not
                        # book page numbers and must never replace unrelated poses.
                        combined=list(previous['images']);known={p['sha256'] for p in combined}
                        known.update(q['sha256'] for p in combined for q in p.get('alternative_sources',[]) if q.get('sha256'))
                        for photo in a['images']:
                            if photo['sha256'] in known:continue
                            alternates={q.get('sha256') for q in photo.get('alternative_sources',[])}
                            matched=next((i for i,p in enumerate(combined) if p['sha256'] in alternates and replacement_reason(photo,p)),None)
                            if matched is None:
                                combined.append({**photo,'number':len(combined)+1})
                            else:
                                combined[matched]={**photo,'number':combined[matched]['number']}
                            known.add(photo['sha256']);known.update(alternates)
                        a['images']=combined;a['expected']=max(a['expected'],len(combined))
                        a['acquired']=len(combined);a['complete_sequence']=False
                        a['missing_numbers']=None if a.get('expected_total_unknown') else a['missing_numbers']
                        a['source_pages']=list(dict.fromkeys(previous.get('source_pages',[])+a['source_pages']))
                        a['minimum_long_edge']=min(max(p['width'],p['height']) for p in combined)
                        existing[a['id']]=a
                        continue
                    old={p['number']:p for p in previous['images']}
                    for photo in a['images']:
                        prior=old.get(photo['number'])
                        if prior:
                            if photo['sha256']==prior['sha256']:
                                # A rerun must preserve an existing verified review.
                                if watermark_status(photo)=='unknown':photo['site_watermark_review']=watermark_review(prior)
                            elif not replacement_reason(photo,prior):
                                photo.clear();photo.update(prior)
                    # A failed or smaller rerun cannot discard already verified files.
                    incoming={p['number']:p for p in a['images']}
                    old.update(incoming);a['images']=sorted(old.values(),key=lambda p:p['number'])
                    a['expected']=max(a['expected'],previous['expected'])
                    a['acquired']=len(a['images'])
                    a['missing_numbers']=sorted(set(range(1,a['expected']+1))-set(old))
                    a['complete_sequence']=not a['missing_numbers']
                    a['resolution_review_required']=True
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
