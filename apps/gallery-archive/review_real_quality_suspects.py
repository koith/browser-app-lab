#!/usr/bin/env python3
"""G-08: compare *actual saved file pixels* for quality suspects against other
saved instances of the same scene. Produce a review report and a contact sheet.
Never automatically overwrite a physical original from a heuristic score.
"""
from __future__ import annotations
import argparse
import json
from pathlib import Path
from PIL import Image, ImageDraw, ImageOps

ROOT=Path(__file__).resolve().parents[1]
SAVE_ROOT=ROOT.parent
HUMAN_REVIEW_THRESHOLD=46  # 256-bit dHash distance, *candidate only*, not identity proof

def dhash(path):
    with Image.open(path) as original:
        gray=ImageOps.exif_transpose(original).convert('L').resize((17,16), Image.Resampling.LANCZOS)
        pix=list(gray.getdata())
        value=0
        for row in range(16):
            for col in range(16):
                value=(value<<1)|int(pix[row*17+col]>pix[row*17+col+1])
        return value

def load_rows():
    rows=[]
    for model in ('yui','mimmi'):
        base=ROOT/(model+'-gallery')
        albums=json.loads((base/'stored-albums.json').read_text(encoding='utf8'))['albums']
        for album in albums:
            for i,p in enumerate(album['images']):
                url=p.get('url','')
                if not url.startswith('stored-albums/'): continue
                path=base/url
                if not path.is_file():continue
                rows.append(dict(model=model,album=album['id'],number=p.get('number',i+1),
                    order=i,sha256=p['sha256'],path=str(path),width=p['width'],
                    height=p['height'],bytes=p['bytes'],origin=p.get('origin_page') or
                    p.get('source_url') or album.get('source','')))
    return rows

def produce(report_path,output_dir):
    audit=json.loads(Path(report_path).read_text(encoding='utf8'))
    flagged=audit.get('suspects',[])
    assert len(flagged)>=3,'Expected at least the three physical-pixel review cases'
    rows=load_rows()
    by_filename={Path(p['path']).name:p for p in rows}
    for p in rows:p['hash']=dhash(p['path'])
    comparisons=[]
    tiles=[]
    for s in flagged:
        key=s['name']
        original=by_filename.get(key)
        assert original and original['model']==s['model'] and original['album']==s['album']
        ranked=sorted((p for p in rows if p['sha256']!=original['sha256']),
                      key=lambda p:((p['hash']^original['hash']).bit_count(),p['album']!=original['album']))
        nearest=ranked[:6]
        neighbors=sorted((p for p in rows if p['model']==original['model']
                      and p['album']==original['album'] and p['sha256']!=original['sha256']),
                    key=lambda p:abs(p['order']-original['order']))[:2]
        candidates=[]
        for p in nearest:
            candidate={k:p[k] for k in ('model','album','number','sha256','width','height','bytes','origin')}
            candidate['dhash_256_distance']=(p['hash']^original['hash']).bit_count()
            candidate['likely_same_scene_candidate']=candidate['dhash_256_distance']<=HUMAN_REVIEW_THRESHOLD
            candidates.append(candidate)
        comparisons.append({
            'suspect':{k:original[k] for k in ('model','album','number','sha256','width','height','bytes','origin')},
            'flag':s['review_flags'],'candidate_threshold_is_not_identity_proof':True,
            'closest_physical_files':candidates,
            'any_unambiguous_same_photo_alternative':False,
            'final_original_vs_alternative_optical_verdict':'requires_visual_identity_and_quality_review',
        })
        tiles.append([(original,'FLAG'),*[(p, 'NEAR '+str((p['hash']^original['hash']).bit_count())) for p in nearest[:4]],
                       (neighbors[0],'NEIGHBOR') if neighbors else (original,'SELF')])
    out=Path(output_dir);out.mkdir(parents=True,exist_ok=True)
    cols=6;cellw=230;cellh=294;pad=12
    canvas=Image.new('RGB',(cols*cellw,len(tiles)*cellh),'#ffffff')
    draw=ImageDraw.Draw(canvas)
    for ri,row in enumerate(tiles):
        for ci,(rec,kind) in enumerate(row):
            xx=ci*cellw;yy=ri*cellh
            with Image.open(rec['path']) as file:
                crop=ImageOps.exif_transpose(file).convert('RGB')
                crop.thumbnail((cellw-2*pad,cellh-90),Image.Resampling.LANCZOS)
                canvas.paste(crop,(xx+(cellw-crop.width)//2,yy+4))
            labels=[kind,f"{rec['model']}/{rec['album'][:24]}",f"{rec['width']}x{rec['height']} {rec['bytes']//1024}KiB",rec['sha256'][:12]]
            for li,label in enumerate(labels):
                draw.text((xx+pad,yy+cellh-84+li*18),label,fill='black')
    canvas.save(out/'g08-actual-pixel-comparison.jpg',quality=85)
    (out/'g08-suspect-comparison.json').write_text(json.dumps({
      'total_saved_files_examined':len(rows),
      'scope':'physically committed GitHub Pages bytes; no remote owner originals inspected',
      'perceptual_hash_is_a_candidate_search_not_visual_quality_proof':True,
      'reviewed_suspects':comparisons,
    },ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    print('G08_REAL_SUSPECT_IMAGE_COMPARISONS',json.dumps({
      'total_files':len(rows),'suspects':len(comparisons),
      'matches':[(c['suspect']['album'],
         [(x['album'],x['dhash_256_distance']) for x in c['closest_physical_files'][:4]])
        for c in comparisons]
    },ensure_ascii=False),flush=True)

if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--audit',default='gallery-visual-quality-audit.json')
    parser.add_argument('--out',default='gallery-g08-physical-review')
    a=parser.parse_args()
    produce(a.audit,a.out)
