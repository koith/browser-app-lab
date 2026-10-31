"""Complete ordinary public editions against SHA-verified saved-work references.

Whole-frame similarity confirms existing photos, never identifies faces. Old
higher quality files stay in their existing slots; source filename numbers are
kept separately from archive order and never called publisher original numbers.
"""
import hashlib
from io import BytesIO
import json
from pathlib import Path
import re
from urllib.parse import urlsplit

from PIL import Image,ImageChops,ImageStat
import requests


def owner_reference(url):
    """Read the user's existing archive API, separately from public crawling.

    The owner's no-index robots policy is not an API authorization check.
    No credential is added and no HTTP denial/redirect is bypassed. Callers
    construct this fixed first-party URL; downloaded bytes must match the
    owner's original/preview SHA before they can become reference evidence.
    """
    target=urlsplit(url)
    if (target.scheme!='https' or target.netloc!='mimmi-private-gallery-free.onrender.com'
            or target.query or target.fragment
            or not re.fullmatch(r'/api/(?:yui/)?media/[a-z0-9][a-z0-9-]{1,100}/[1-9][0-9]*/preview',target.path)):
        raise ValueError('Only the existing fixed owner-archive reference API is allowed')
    with requests.get(url,timeout=(12,45),allow_redirects=False,stream=True) as response:
        response.raise_for_status()
        if response.status_code!=200:raise ValueError('Owner reference redirected or unavailable')
        data=bytearray()
        for chunk in response.iter_content(65536):
            data.extend(chunk)
            if len(data)>35_000_000:raise ValueError('Owner reference exceeds bounded image size')
        return bytes(data)


def visual_error(left,right):
    with Image.open(BytesIO(left)) as a,Image.open(BytesIO(right)) as b:
        if abs((a.width/a.height)/(b.width/b.height)-1)>.012:return 255
        # Comparison alone ignores a bottom site watermark, without editing
        # or removing any pixel from the archived source byte file.
        a=a.convert('RGB').resize((64,64)).crop((0,0,64,55))
        b=b.convert('RGB').resize((64,64)).crop((0,0,64,55))
        return max(ImageStat.Stat(ImageChops.difference(a,b)).mean)


def collect_work(book,previous,client,out,budget,seen_sha,model,reference_reader=None,reference_paths=None):
    from direct_photo_pipeline import page_images,inspect,atomic_bytes,safe_page
    aid=book['id'];claimed=book['public_web_edition_photos']
    if type(claimed) is not int or not 3<=claimed<=500:raise ValueError('Bounded verified public work size required')
    info={'id':aid,'source':book['source'],'known_web_edition_photos':claimed,
          'publisher_original_numbering_known':False,'individual_files_saved':0,
          'saved_reference_anchors':0,'failures':[],'engine':'public_pagination_with_verified_visual_references'}
    if len({p['sha256'] for p in previous})>=claimed:
        info['already_saved_web_edition']=True;return None,info
    previous_unique=len({p['sha256'] for p in previous})
    if not previous or previous_unique>20:
        info['failures'].append('Focused recovery requires an existing low-count saved work');return None,info
    if claimed-previous_unique>budget:
        info['failures'].append('Defer whole work to next bounded batch, do not publish a truncated edition');return None,info
    refs=[];reference_hashes=set();reference_dir=out/'references'/aid;reference_dir.mkdir(parents=True,exist_ok=True)
    try:
        for photo in previous:
            # Old ledgers sometimes assign one exact SHA to two numbers. Those
            # are one reference cut, not competing visual matches.
            if photo['sha256'] in reference_hashes:continue
            reference_hashes.add(photo['sha256'])
            digest=photo.get('preview_sha256') or photo['sha256'];path=reference_dir/(digest+'.bin')
            if path.exists():raw=path.read_bytes()
            elif reference_paths and photo['sha256'] in reference_paths:
                # The user already has this exact original committed locally.
                # Verify its SHA below, without depending on a sleeping gateway.
                raw=Path(reference_paths[photo['sha256']]).read_bytes()
            else:
                route='/api/yui' if model=='yui' else '/api'
                raw=(reference_reader or owner_reference)(f'https://mimmi-private-gallery-free.onrender.com{route}/media/{aid}/{photo["number"]}/preview')
            if hashlib.sha256(raw).hexdigest() not in (digest,photo['sha256']):
                raise ValueError('Saved reference did not match declared SHA')
            atomic_bytes(path,raw);refs.append((photo,raw))
    except Exception as e:
        info['failures'].append('reference_'+type(e).__name__);return None,info
    queue=[book['source']];visited=set();urls=[]
    while queue and len(visited)<45:
        page=queue.pop(0)
        if page in visited:continue
        visited.add(page)
        try:
            r=client.get(page);images,more,status=page_images(r.content,page,model)
            if status!='scoped_public_page':raise ValueError(status)
            for image in images:
                if image not in urls:urls.append(image)
            for link in more:
                if safe_page(link) and link not in visited and link not in queue:queue.append(link)
        except Exception as e:
            info['failures'].append('page_'+type(e).__name__);break
    numbered={}
    for url in urls:
        match=re.search(r'PixiBB\.COM-(\d{1,4})\.(?:jpe?g|webp|png)$',url,re.I)
        if not match:continue
        n=int(match[1])
        if n in numbered and numbered[n]!=url:
            info['failures'].append('Conflicting public filename number');return None,info
        numbered[n]=url
    info['observed_filename_numbers']=sorted(numbered);info['pages']=len(visited)
    info['unobserved_source_numbers']=sorted(set(range(1,claimed+1))-set(numbered))
    anchors=set();pending=[];pending_bytes=0;uncertain=[];decoded=set();failed=set();prior_by_sha={p['sha256']:p for p in previous}
    for source_number,url in sorted(numbered.items()):
        try:
            raw=client.get(url).content;meta,preview,_=inspect(raw);decoded.add(source_number)
            pending_bytes+=len(raw)+len(preview)
            if pending_bytes>384*1024*1024:raise ValueError('Bounded work memory limit exceeded')
            exact=prior_by_sha.get(meta['sha256'])
            errors=sorted((visual_error(raw,data),p['number'],p) for p,data in refs)
            best=errors[0]
            if exact or (best[0]<=4 and (len(errors)==1 or errors[1][0]-best[0]>=2)):
                old=exact or best[2];anchors.add(old['number'])
                info.setdefault('saved_cut_correspondence',[]).append({'source_file_number':source_number,
                    'owner_archive_number':old['number'],'owner_sha256':old['sha256'],
                    'source_sha256':meta['sha256'],'whole_frame_visual_error':best[0]})
                # Never trade a larger unwatermarked saved original for a
                # smaller site-watermarked rendition of exactly the same cut.
                if meta['width']*meta['height']<=old['width']*old['height']:continue
                pending.append((source_number,url,raw,meta,preview,old['number']))
            elif best[0]<9:
                uncertain.append(source_number)
                atomic_bytes(out/'review'/aid/(str(source_number)+'.'+meta['extension']),raw)
            elif meta['sha256'] not in seen_sha:
                pending.append((source_number,url,raw,meta,preview,None))
        except Exception as e:
            failed.add(source_number);info['failures'].append({'source_number':source_number,'reason':type(e).__name__})
        if source_number%20==0:
            print('PUBLIC_EDITION_ACTUAL_DECODE_PROGRESS',aid,source_number,'/',claimed,'saved_cut_anchors',len(anchors),flush=True)
    info['saved_reference_anchors']=len(anchors);info['uncertain_source_numbers']=uncertain
    info['unresolved_source_numbers']=sorted(set(info['unobserved_source_numbers'])|set(uncertain)|failed)
    if len(anchors)<3:
        info['failures'].append('Work withheld: fewer than 3 clear saved-cut anchors')
        return None,info
    if len(pending)>budget:
        info['failures'].append('Verified missing files exceed remaining bounded batch; defer whole work')
        return None,info
    images=[];next_number=max(p['number'] for p in previous)+1
    for source_number,url,raw,meta,preview,replacement in pending:
        if meta['sha256'] in seen_sha:continue
        number=replacement or next_number
        if replacement is None:next_number+=1
        ext=meta.pop('extension');filename=f'{number:05d}-{meta["sha256"][:16]}'
        key=f'originals/{aid}/{filename}.{ext}';thumbnail=f'previews/{aid}/{filename}.webp'
        atomic_bytes(out/key,raw);atomic_bytes(out/thumbnail,preview)
        row={**meta,'number':number,'key':key,'preview':thumbnail,
             'preview_bytes':len(preview),'preview_sha256':hashlib.sha256(preview).hexdigest(),
             'source_photo_number':source_number,'source_numbering':'public_web_filename_not_publisher_original',
             'higher_resolution_replacement':replacement is not None,
             'work_identity_saved_cut_anchors':len(anchors),'watermark_review':'site_watermarked_public_edition'}
        images.append(row);seen_sha.add(row['sha256'])
    info['individual_files_saved']=len(images);info['source_files_decoded']=len(decoded)
    info['source_edition_all_files_accounted_for']=not info['unresolved_source_numbers']
    return ({'id':aid,'title':book['title'],'expected':None,'complete':False,'images':images} if images else None),info
