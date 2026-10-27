"""Optional free OCR evidence of gallery-site marks. No match means unknown.

This never asserts watermark absence or alters an image. Only confident text
in an outer image margin can establish presence; publisher signatures do not.
"""
import argparse,csv,hashlib,io,json,re,subprocess
from pathlib import Path
from PIL import Image

SITE_TEXT=re.compile(r'(?:pixibb(?:\.com)?|misskon(?:\.com)?|mrcong(?:\.com)?|4kup(?:\.net)?|girl-atlas(?:\.com)?|v2ph(?:\.com)?|jliji(?:\.com)?)',re.I)
def review(path,photo):
    if hashlib.sha256(path.read_bytes()).hexdigest()!=photo['sha256']:
        raise ValueError('Watermark evidence file checksum mismatch')
    unknown={'status':'unknown'}
    try:
        r=subprocess.run(['tesseract',str(path),'stdout','--psm','11','tsv'],capture_output=True,text=True,timeout=30)
    except (OSError,subprocess.TimeoutExpired):return unknown
    if r.returncode:return unknown
    with Image.open(path) as im:width,height=im.size
    for row in csv.DictReader(io.StringIO(r.stdout),delimiter='\t'):
        text=row.get('text','').strip()
        if not SITE_TEXT.fullmatch(text):continue
        if float(row['conf'])<80:continue
        x,y,w,h=(int(row[k]) for k in ['left','top','width','height'])
        if not (y>=height*.85 or y+h<=height*.12 or x+w<=width*.1 or x>=width*.9):continue
        return {'status':'present','sha256':photo['sha256'],
                'evidence':'Tesseract recognized gallery-site text in an outer image margin; no pixel edits.',
                'matched_text':text,'confidence':float(row['conf']),'bounds':[x,y,w,h]}
    return unknown

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('folder',type=Path);args=parser.parse_args()
    p=args.folder/'manifest.json';m=json.loads(p.read_text())
    from concurrent.futures import ThreadPoolExecutor
    from photo_quality_policy import watermark_status
    def one(photo):
        path=(args.folder/photo['file']).resolve()
        if not path.is_relative_to(args.folder.resolve()):raise ValueError('Unsafe review file path')
        if watermark_status(photo)=='unknown':photo['site_watermark_review']=review(path,photo)
        return photo
    with ThreadPoolExecutor(max_workers=3) as pool:m['images']=list(pool.map(one,m['images']))
    p.write_text(json.dumps(m,ensure_ascii=False,indent=2)+'\n')
    print('SITE_MARK_REVIEW_PRESENT',sum(watermark_status(p)=='present' for p in m['images']),'UNKNOWN',sum(watermark_status(p)=='unknown' for p in m['images']),'ABSENCE_NOT_INFERRED')
