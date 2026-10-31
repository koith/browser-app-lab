"""Reconstruct one reviewed work's exact delta for read-only remote verification.

No image upload or live catalogue mutation is performed. A missing remote file
fails verification; it is never replaced by a different SHA or a thumbnail.
"""
import argparse
import json
from pathlib import Path
import re

from direct_photo_pipeline import PublicSession,safe_page
from visual_public_work import collect_work

ROOT=Path(__file__).resolve().parents[2]


def reviewed_work(root,owner,model,aid):
    if (model not in ('mimmi','yui') or owner.get('model')!=model
            or owner.get('schema_version')!=1 or not re.fullmatch(r'[a-z0-9][a-z0-9-]{1,100}',aid)):
        raise ValueError('Wrong existing owner work scope')
    document=json.loads((root/f'apps/{model}-gallery/public-work-pages.json').read_text())
    book=next((a for a in document['albums'] if a['id']==aid),None)
    previous=next((a for a in owner.get('albums',[]) if a['id']==aid),None)
    if (document.get('model')!=model or not book or book.get('visual_reference_required') is not True
            or not safe_page(book.get('source','')) or not previous or not previous.get('images')):
        raise ValueError('Only an already reviewed source and an existing saved work are allowed')
    return book,previous


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--root',type=Path,default=ROOT)
    p.add_argument('--model',choices=['mimmi','yui'],required=True);p.add_argument('--work',required=True)
    p.add_argument('--owner',type=Path,required=True);p.add_argument('--out',type=Path,required=True)
    p.add_argument('--github-output',type=Path,required=True);args=p.parse_args()
    owner=json.loads(args.owner.read_text());book,previous=reviewed_work(args.root,owner,args.model,args.work)
    base=args.root/f'apps/{args.model}-gallery'
    public=json.loads((base/'stored-albums.json').read_text())
    refs={q['sha256']:base/q['url'] for a in public['albums'] for q in a['images']}
    seen={q['sha256'] for a in owner['albums'] for q in a['images']}
    work,info=collect_work(book,previous['images'],PublicSession(delay=1.2),args.out,500,seen,args.model,reference_paths=refs)
    albums=[work] if work else [];count=sum(len(a['images']) for a in albums)
    metadata=args.out/'metadata';metadata.mkdir(parents=True,exist_ok=True)
    (metadata/'catalog.json').write_text(json.dumps({'schema_version':1,'model':args.model,
        'storage':'owner-private-terabox-sha-verified-bytes','albums':albums},ensure_ascii=False,indent=2)+'\n')
    upgrades=sum(bool(q.get('higher_resolution_replacement')) for a in albums for q in a['images'])
    (metadata/'collection-audit.json').write_text(json.dumps({'model':args.model,'results':[info],
        'new_local_individual_files':count,'new_photo_positions':count-upgrades,'higher_resolution_replacements':upgrades,
        'remote_verified_files':0,'gallery_open_verified_files':0,'photo_bundles_created':0},ensure_ascii=False,indent=2)+'\n')
    print('EXISTING_WORK_RECONSTRUCTED_LOCAL_ONLY',args.model,args.work,count,'REMOTE_VERIFIED',0,'GALLERY_ADDED',0,flush=True)
    if info.get('failures'):raise ValueError('Work reconstruction failed; no queue was admitted')
    with args.github_output.open('a') as output:output.write('changed='+str(bool(count)).lower()+'\n')
