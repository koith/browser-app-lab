#!/usr/bin/env python3
"""G-07: direct, individual-file capture of current publicly visible creator posts.

The recorded 2026-11-03 SNS feed does not cover Nov 7-12 posts. Read only
actual public https://teapawt.net/super_yuisan/media author cards, follow at
most two *observed* pagination cursors, download and decode first-party
pbs.twimg.com photos, and stage immutable SHA files for the existing Pages
publisher. No ZIP, no auth, no generated media links or reposts.
"""
from __future__ import annotations
import argparse,hashlib,json,shutil
from pathlib import Path
from PIL import Image
from collect_teapawt_public import capture

ROOT=Path(__file__).resolve().parents[2]

def collect(stage,max_pages=2,max_photos=44,root=ROOT,fetch=None):
    stage=Path(stage)
    source={'id':'public-yui-sns','kind':'teapawt',
            'url':'https://teapawt.net/super_yuisan/media','account':'super_yuisan'}
    capture_fn=fetch or capture
    folder=stage/'source-author-photos'
    report=capture_fn(source,folder,max_pages=max_pages,max_photos=max_photos,workers=3)
    prior=json.loads((Path(root)/'apps/yui-gallery/owner-index.json').read_text())
    local=json.loads((Path(root)/'apps/yui-gallery/stored-albums.json').read_text())
    existing={p['sha256'] for a in prior['albums'] for p in a['images']}
    existing|={p['sha256'] for a in local['albums'] for p in a['images']}
    previous=next((a for a in prior['albums'] if a['id']=='public-yui-sns'),None)
    number=max((p['number'] for p in (previous or {}).get('images',[])),default=0)+1
    new=[]
    for file in sorted(folder.iterdir()):
        if file.suffix.lower() not in ('.jpg','.jpeg','.png','.webp') or not file.is_file():continue
        sidecar=file.with_suffix('.json')
        identity=json.loads(sidecar.read_text()) if sidecar.is_file() else {}
        if identity.get('author',{}).get('screen_name')!='super_yuisan':continue
        # Preserve the exact first-party public photo URL seen in the author
        # card; never silently attribute every image to the profile landing.
        observed_url=identity.get('observed_media_url')
        from collect_teapawt_public import safe_media_url
        if not isinstance(observed_url,str) or safe_media_url(observed_url,source['url'])!=observed_url:
            continue
        raw=file.read_bytes();sha=hashlib.sha256(raw).hexdigest()
        if sha in existing or len(raw)<5000 or len(raw)>8_000_000:continue
        if file.stem!=sha:raise ValueError('source filename SHA mismatch')
        with Image.open(file) as image:image.verify()
        with Image.open(file) as image:
            image.load()
            w,h=image.size
            if min(w,h)<320:continue
            fmt=image.format
        ext={'JPEG':'jpg','PNG':'png','WEBP':'webp'}.get(fmt)
        if not ext:continue
        rel='originals/public-yui-sns/'+f'{number:05d}-{sha[:16]}.{ext}'
        dest=stage/rel;dest.parent.mkdir(parents=True,exist_ok=True)
        shutil.copyfile(file,dest)
        new.append({'number':number,'key':rel,'sha256':sha,'bytes':len(raw),
                    'width':w,'height':h,'extension':ext,'source_url':observed_url})
        number+=1;existing.add(sha)
    meta=stage/'metadata';meta.mkdir(parents=True,exist_ok=True)
    (meta/'catalog.json').write_text(json.dumps({'schema_version':1,'model':'yui',
       'albums':[{'id':'public-yui-sns','title':'심유이 공식 공개 SNS 사진','images':new}]},
        ensure_ascii=False,indent=2)+'\n')
    report={**report,'new_SHA_not_in_existing_owner_or_Pages':len(new),
            'public_own_author_card_only':True,'remote_readback_verified':False,
            'gallery_open_verified':False}
    (meta/'collection-audit.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    print('G07_NEW_OFFICIAL_PUBLIC_SOCIAL_PHYSICAL_SHA',json.dumps(report),flush=True)
    return report

if __name__=='__main__':
    a=argparse.ArgumentParser()
    a.add_argument('--stage',type=Path,required=True)
    a.add_argument('--max-pages',type=int,default=2)
    a.add_argument('--max-photos',type=int,default=44)
    args=a.parse_args()
    if not 1<=args.max_pages<=4 or not 1<=args.max_photos<=80:raise SystemExit('bounded')
    collect(args.stage,args.max_pages,args.max_photos)
