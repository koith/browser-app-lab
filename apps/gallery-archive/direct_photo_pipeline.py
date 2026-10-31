"""Collect normal public pages directly into resumable INDIVIDUAL owner files.

No photo ZIP, artifact, source hotlink, login, CAPTCHA, invented page/image URL,
or unverified overwrite. Cloud publication is a separate SHA-readback transaction.
"""
import argparse
from collections import defaultdict
from datetime import datetime, timezone
import hashlib
from io import BytesIO
import json
from pathlib import Path
import re
import sys
from urllib.parse import urljoin, urlsplit, urlunsplit, parse_qsl, urlencode

from bs4 import BeautifulSoup
from PIL import Image, ImageStat

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'apps/yui-gallery'))
from public_photo_archive import PublicSession,public_failure
from collect_private_batch import allowed_url, safe_reencoded_public_preview

MODEL_PATTERNS={'mimmi':re.compile(r'(?<![a-z])mimmi(?![a-z])|밈미|밈미',re.I),
                'yui':re.compile(r'(?<![a-z])yui(?![a-z])|유이|심혜성|super_yuisan',re.I)}
PAGE_HOSTS={'djawaphoto.com','www.djawaphoto.com','cosplay.pixibb.com','sexy.pixibb.com','www.v2ph.com','v2ph.com',
            'blog.hacosta.co.jp','www.gamersky.com','www.inven.co.kr','photo.inven.co.kr',
            'www.ajunews.com','sportsseoul.com','www.sportsseoul.com','crazygiant.imweb.me','teapawt.net','www.shypetal.com'}
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


def public_full_variant(url):
    p=urlsplit(url)
    if p.hostname=='upload3.inven.co.kr':
        return urlunsplit(p._replace(query=urlencode([(k,v) for k,v in parse_qsl(p.query) if k!='MW'])))
    return url


def same_variant(old_raw,new_raw):
    """Same observed public asset only; never identify people or merge works."""
    with Image.open(BytesIO(old_raw)) as old, Image.open(BytesIO(new_raw)) as new:
        if abs((old.width/old.height)/(new.width/new.height)-1)>.01:return False
        a=old.convert('RGB').resize((64,64));b=new.convert('RGB').resize((64,64))
        from PIL import ImageChops
        return max(ImageStat.Stat(ImageChops.difference(a,b)).mean)<=5


def page_images(raw,url,model):
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
        if tag.find_parent(class_=re.compile(r'related|recommend|comment|advert|sidebar',re.I)):continue
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


def atomic_bytes(path,data):
    path.parent.mkdir(parents=True,exist_ok=True)
    if path.exists():
        if path.read_bytes()!=data:raise ValueError('Existing file cannot be overwritten')
        return
    tmp=path.with_name(path.name+'.pending');tmp.write_bytes(data);tmp.replace(path)


def collect(root,model,owner,out,max_new=180,max_pages=24,client=None,focused_only=False,album_ids=None):
    root=Path(root);out=Path(out)
    if owner.get('model')!=model or owner.get('schema_version')!=1 or not owner.get('albums'):
        raise ValueError('Current owner catalog required; do not assume empty archive')
    base=root/'apps'/(model+'-gallery')
    inputs=(['official-previews.json','v2ph-actor-previews.json','pixibb-public-previews.json'] if model=='mimmi' else ['additional-source-albums.json'])+['public-work-pages.json']
    old_albums={a['id']:a for a in owner['albums']};saved_sha={p['sha256'] for a in owner['albums'] for p in a['images']}
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
            pages=[u for u in a.get('source_pages',[]) if safe_page(u)]
            source=a.get('source') or next(iter(pages),None)
            if not source or not safe_page(source):continue
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
    client=client or PublicSession(delay=.8)
    results=[];new_albums=[];new_total=0;downloaded_now=0;seen_urls=set();seen_sha=set(saved_sha)
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
        key=lambda a:(a.get('priority',100),len(old_albums.get(a['id'],{}).get('images',[])),a['id']))
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
        queue=list(dict.fromkeys([book['source']]+[u for u in book.get('source_pages',[]) if safe_page(u)]));visited=set();errors=[];candidate_count=0;unreviewed_count=0
        while queue and len(visited)<max_pages and new_total<max_new:
            page=queue.pop(0)
            if page in visited:continue
            visited.add(page)
            try:
                response=client.get(page);urls,more,status=page_images(response.content,page,model)
                for p in more:
                    if p not in visited and p not in queue:queue.append(p)
                if status!='scoped_public_page':errors.append({'page':page,'reason':status});continue
            except Exception as e:
                errors.append({'page':page,'reason':type(e).__name__,**public_failure(e)});break
            for url in urls:
                if new_total>=max_new:break
                candidate_count+=1
                old=historic.get((aid,url))
                if book.get('curated_images_only') and not old:
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
                    if variant:
                        if p['sha256'] in seen_sha:continue
                        reference=client.get(old['url']).content
                        if hashlib.sha256(reference).hexdigest()!=old['sha256'] or not same_variant(reference,raw):
                            raise ValueError('full_variant_identity_or_visual_match_failed')
                        if former and p['width']*p['height']<=former['width']*former['height']:continue
                        p['variant_of_sha256']=old['sha256'];p['higher_resolution_replacement']=bool(former)
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
                         'numbering_provenance':'published_source_order' if old else 'archive_append_order_not_publisher_number'}
                    images.append(row);new_total+=1;downloaded_now+=1
                    with journal.open('a') as log:log.write(json.dumps({'album':aid,'number':number,'source':url,'photo':row,'remote_verified':False})+'\n')
                except Exception as e:errors.append({'number':number,'url':url,'reason':type(e).__name__,**public_failure(e)})
        if images:new_albums.append({'id':aid,'title':book.get('title') or aid,'publisher':book.get('publisher'),
            'expected':None,'complete':False,'images':images})
        results.append({'id':aid,'engine':'requests_scoped_public_pagination','pages':len(visited),
                        'published_image_candidates':candidate_count,'individual_files_saved':len(images),
                        'unreviewed_legacy_image_candidates_skipped':unreviewed_count,
                        'failures':errors,'cloud_readback_pass':0,'gallery_open_pass':0})
        print('DIRECT_INDIVIDUAL_PHOTO_COLLECTION',model,aid,'saved',len(images),'failures',len(errors),flush=True)
    catalog={'schema_version':1,'model':model,'storage':'owner-private-terabox-sha-verified-bytes','albums':new_albums}
    metadata=out/'metadata';metadata.mkdir(parents=True,exist_ok=True)
    (metadata/'catalog.json').write_text(json.dumps(catalog,ensure_ascii=False,indent=2)+'\n')
    report={'model':model,'generated_at':datetime.now(timezone.utc).isoformat(),'new_local_individual_files':new_total,
            'downloaded_new_this_invocation':downloaded_now,'resumed_verified_staged_files':new_total-downloaded_now,
            'new_photo_positions':sum(not p.get('higher_resolution_replacement') for a in new_albums for p in a['images']),
            'higher_resolution_replacements':sum(bool(p.get('higher_resolution_replacement')) for a in new_albums for p in a['images']),
            'remote_verified_files':0,'gallery_open_verified_files':0,'photo_bundles_created':0,'results':results}
    (metadata/'collection-audit.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    return report


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--root',type=Path,default=ROOT);p.add_argument('--model',choices=['mimmi','yui'],required=True);p.add_argument('--owner',type=Path,required=True);p.add_argument('--out',type=Path,required=True);p.add_argument('--max-new',type=int,default=180);p.add_argument('--max-pages',type=int,default=24);p.add_argument('--focused-only',action='store_true');p.add_argument('--album-id',action='append',default=[]);a=p.parse_args()
    if not 1<=a.max_new<=500 or not 1<=a.max_pages<=60:raise SystemExit('Bounded collection budget required')
    report=collect(a.root,a.model,json.loads(a.owner.read_text()),a.out,a.max_new,a.max_pages,focused_only=a.focused_only,album_ids=a.album_id)
    print('DIRECT_FILE_COLLECTION_COMPLETE',report['model'],report['new_local_individual_files'],'REMOTE_VERIFIED',0,'GALLERY_VERIFIED',0)
