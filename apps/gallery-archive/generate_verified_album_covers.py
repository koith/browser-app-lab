#!/usr/bin/env python3
"""G-10: derive cover crop and publisher-work SHA evidence from real saved files.

Never classify a person's identity; never fetch or replace originals. A locally
committed SHA-verified photo from the same recorded work is used before owner
metadata-only fallback. Current manual cover curation is preserved.
"""
from __future__ import annotations
import argparse,hashlib,json
from pathlib import Path
import cv2
from PIL import Image,ImageOps

ROOT=Path(__file__).resolve().parents[1]
FRONT=cv2.CascadeClassifier(cv2.data.haarcascades+'haarcascade_frontalface_default.xml')
EYES=cv2.CascadeClassifier(cv2.data.haarcascades+'haarcascade_eye_tree_eyeglasses.xml')
assert not FRONT.empty() and not EYES.empty()

def framed(w,h,face):
    x,y,fw,fh=face
    s=max(300/w,200/h)
    px=[]
    for total,center,screen,target in ((w,x+fw/2,300,.5),(h,y+fh/2,200,.47)):
        overflow=total*s-screen
        delta=max(0,min(overflow,center*s-screen*target))
        px.append(round(delta/overflow*100,3) if overflow>0.001 else 50)
    return px

def face_candidate(file):
    with Image.open(file) as orig:
        width,height=orig.size
        im=ImageOps.exif_transpose(orig).convert('RGB')
        im.thumbnail((850,850),Image.Resampling.LANCZOS)
        import numpy as np
        mat=np.asarray(im)
    gray=cv2.equalizeHist(cv2.cvtColor(mat,cv2.COLOR_RGB2GRAY))
    rectangles,reject,weights=FRONT.detectMultiScale3(
      gray,scaleFactor=1.1,minNeighbors=5,minSize=(32,32),outputRejectLevels=True)
    found=[]
    sx=width/im.width;sy=height/im.height
    for box,weight in zip(rectangles,weights):
        x,y,w,h=[int(z) for z in box]
        if float(weight)<3.5:continue
        eyes=EYES.detectMultiScale(gray[y:y+max(1,int(h*.65)),x:x+w],minNeighbors=3)
        if len(eyes)<1:continue
        face=[int(round(x*sx)),int(round(y*sy)),int(round(w*sx)),int(round(h*sy))]
        found.append((float(weight)+max(0,w*h/10000),face))
    if not found:return None
    score,face=max(found,key=lambda item:item[0])
    return face,framed(width,height,face),round(score,3)

def secure_local_record(root,album,record):
    url=record.get('url','')
    if (not isinstance(url,str) or not url.startswith('stored-albums/'+album['id']+'/')
        or any(x in url for x in ('..','?','#'))):
        return None
    file=(root/url).resolve()
    if not file.is_relative_to(root.resolve()) or not file.is_file():return None
    data=file.read_bytes()
    if (hashlib.sha256(data).hexdigest()!=record.get('sha256')
        or len(data)!=record.get('bytes')):return None
    with Image.open(file) as image:
        image.load()
        if tuple(image.size)!=(record.get('width'),record.get('height')):return None
    return file

def run(out):
    result={}
    for model in ('mimmi','yui'):
        root=ROOT/(model+'-gallery')
        local=json.loads((root/'stored-albums.json').read_text(encoding='utf8'))
        owner=json.loads((root/'owner-index.json').read_text(encoding='utf8'))
        excluded=json.loads((root/'identity-exclusions.json').read_text(encoding='utf8'))
        deny_ids=set(excluded.get('excluded_album_ids',[]))|set(excluded.get('excluded_source_ids',[]))
        deny_sha=set(excluded.get('excluded_image_sha256',[]))
        current=json.loads((root/'album-covers.json').read_text(encoding='utf8'))
        existing=current.get('covers',{})
        local_by={a['id']:a for a in local['albums']}
        owner_by={a['id']:a for a in owner['albums']}
        union={**local_by,**owner_by}
        # A local legacy folder can be mislabeled: Yui/v04 has ten JPEGs that
        # exactly belong to the Teddy Bear owner original, not to v04's
        # distinct SHA-verified owner #1. Do not reuse cross-owner bytes merely
        # because the file physically sits in an old album directory.
        owner_sha_album={}
        for origin_id,owner_work in owner_by.items():
            for item in owner_work.get('images',[]):
                owner_sha_album.setdefault(item.get('sha256'),set()).add(origin_id)
        def local_is_correct_work(album_id,photo):
            owners=owner_sha_album.get(photo.get('sha256'),set())
            return not owners or album_id in owners
        covers={}
        counts={'manual_kept':0,'face_selected':0,'same_work_local_fallback':0,
          'owner_sha_only_fallback':0,'total_visible_source_works':0,'refused_incorrect_sha':0}
        for album_id in sorted(union):
            if album_id in deny_ids:continue
            local_album=local_by.get(album_id)
            owner_album=owner_by.get(album_id)
            originals=((owner_album or {}).get('images') or [])
            persisted=((local_album or {}).get('images') or [])
            candidates=originals+persisted
            candidates=[p for p in candidates if p.get('sha256') not in deny_sha]
            if not candidates:continue
            counts['total_visible_source_works']+=1
            curated=existing.get(album_id)
            if curated and any(p.get('sha256')==curated.get('sha256') for p in candidates):
                covers[album_id]=curated
                counts['manual_kept']+=1
                continue
            eligible=[]
            for num,photo in enumerate(persisted[:8]):
                if photo.get('sha256') in deny_sha or not local_is_correct_work(album_id,photo):continue
                file=secure_local_record(root,local_album,photo)
                if file is None:
                    counts['refused_incorrect_sha']+=1
                    continue
                face=face_candidate(file)
                if face:
                    box,position,confidence=face
                    # Prefer a recognizable portrait on an already-saved
                    # same-work file, not another album's/artist's photo.
                    eligible.append((confidence,num,photo,box,position))
            if eligible:
                confidence,num,photo,box,position=max(
                   eligible,key=lambda x:(x[0],-x[1]))
                covers[album_id]={
                   'sha256':photo['sha256'],'number':photo.get('number',num+1),
                   'width':photo['width'],'height':photo['height'],
                   'face':box,'position':position,'fit':'cover',
                   'method':'verified_same_work_local_face_and_eye_region',
                   'confidence':confidence,'not_identity_recognition':True}
                counts['face_selected']+=1
                continue
            # A real saved physical same-work file is safer than choosing an
            # album's borrowed cover from a similarly named mirror entry.
            local_first=next(((idx,p) for idx,p in enumerate(persisted)
                              if p.get('sha256') not in deny_sha
                                 and local_is_correct_work(album_id,p)
                                 and secure_local_record(root,local_album,p)),None) if local_album else None
            if local_first is not None:
                idx,photo=local_first
                counts['same_work_local_fallback']+=1
                method='sha_verified_same_work_local_no_face_proven'
            else:
                photo=next(p for p in originals if p.get('sha256') not in deny_sha)
                idx=0
                counts['owner_sha_only_fallback']+=1
                method='owner_index_same_work_sha_only_no_pixel_decode'
            covers[album_id]={
               'sha256':photo['sha256'],'number':photo.get('number',idx+1),
               'width':photo['width'],'height':photo['height'],
               'position':[50,20],'fit':'cover',
               'method':method,'not_identity_recognition':True}
        result[model]={'schema_version':2,'source_pixels_unchanged':True,
           'not_identity_recognition':True,'source_is_same_work_sha_metadata':True,
           'covers':covers,
           'coverage':counts}
        print('G10_VERIFIED_COVER_SELECTION',model,json.dumps(counts),flush=True)
        assert len(covers)==counts['total_visible_source_works']
        assert counts['refused_incorrect_sha']==0
    out=Path(out)
    out.mkdir(parents=True,exist_ok=True)
    for model,data in result.items():
        (out/f'{model}-album-covers.json').write_text(
         json.dumps(data,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    return result

if __name__=='__main__':
    p=argparse.ArgumentParser()
    p.add_argument('--out',default='gallery-g10-cover-review')
    a=p.parse_args()
    run(Path(a.out))
