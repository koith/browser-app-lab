"""Prefer a larger already collected web file for a conservatively matched photo.

No image is reencoded. Keep both input editions. Uncertain matches stay unchanged.
This does not certify any publisher master or remove source files.
"""
import argparse,hashlib,json,shutil
from pathlib import Path
from PIL import Image,ImageChops,ImageStat,ImageFilter,ImageOps
from photo_quality_policy import replacement_reason,watermark_review

def signature(path,rotation=0):
    with Image.open(path) as im:
        if rotation:im=im.rotate(-rotation,expand=True)
        rgb=im.convert('RGB').resize((32,32));gray=im.convert('L').resize((9,8))
        data=list(gray.getdata());bits=0
        for y in range(8):
            for x in range(8):bits=(bits<<1)|int(data[y*9+x]>data[y*9+x+1])
        return bits,rgb


def optical_detail(path, rotation=0):
    """Decode actual pixels at the same display scale for pairwise clarity."""
    with Image.open(path) as source:
        photo=ImageOps.exif_transpose(source).convert('RGB')
        if rotation:photo=photo.rotate(-rotation,expand=True)
        width,height=photo.size
        photo.thumbnail((560,560), Image.Resampling.LANCZOS)
        gray=ImageOps.grayscale(photo)
        pad_w=max(1,gray.width//10);pad_h=max(1,gray.height//10)
        gray=gray.crop((pad_w,pad_h,gray.width-pad_w,gray.height-pad_h))
        contrast=ImageStat.Stat(gray).stddev[0]
        detail=ImageStat.Stat(ImageChops.difference(
            gray,gray.filter(ImageFilter.GaussianBlur(1.2)))).mean[0]
        return {'width':width,'height':height,
                'high_frequency':detail,
                'detail_index':detail/max(contrast,4.0)}


def paired_optical_relation(old_file,new_file,old_rotation=0,new_rotation=0):
    """A unique same-frame match is already proven by signature() and
    select_match(). This measures optical detail; dimensions alone never win.

    A rescaled copy with no new detail remains UNPROVEN, not 'higher'.
    Unknown or close scores retain the original unless independently
    authenticated watermark evidence breaks a same-size quality tie.
    """
    old=optical_detail(old_file,old_rotation)
    new=optical_detail(new_file,new_rotation)
    if (new['detail_index']>old['detail_index']*1.28
            and new['high_frequency']>old['high_frequency']+0.45):
        return 'higher'
    if (old['detail_index']>new['detail_index']*1.28
            and old['high_frequency']>new['high_frequency']+0.45):
        return 'lower'
    if ((old['width'],old['height'])==(new['width'],new['height'])
            and abs(old['detail_index']-new['detail_index'])
            <=max(0.012,min(old['detail_index'],new['detail_index'])*0.18)):
        return 'comparable'
    return None


def select_match(matches):
    """Require a unique whole-frame match, including near-identical poses."""
    if not matches:return None
    by_hash=sorted(matches,key=lambda row:(row[0],row[1]))
    if len(by_hash)==1:return by_hash[0]
    # Compression can flip several dHash bits in a very smooth scene. Accept
    # this case only when the independent full-frame RGB difference is below
    # one 8-bit level and every competing pose differs by at least three.
    by_error=sorted(matches,key=lambda row:row[1])
    if by_error[0][1]<1 and by_error[1][1]>=3 and by_error[1][1]>=4*by_error[0][1]:return by_error[0]
    if by_hash[1][0]>by_hash[0][0]+2 and by_hash[0]==by_error[0]:return by_hash[0]
    return None

def merge(primary,alternative,out):
    a=json.loads((primary/'manifest.json').read_text());b=json.loads((alternative/'manifest.json').read_text())
    if b.get('ai_enhanced') and not a.get('ai_enhanced'):
        raise ValueError('AI-enhanced copies cannot replace a non-AI edition')
    # Different visible proxy URLs can return exactly the same bytes. Treat
    # byte-identical candidates once so they do not create false ambiguity.
    unique={}
    for photo in b['images']:
        with Image.open(alternative/photo['file']) as image:
            pixels=hashlib.sha256(str(image.size).encode()+image.convert('RGB').tobytes()).hexdigest()
        unique.setdefault(pixels,photo)
    references=[]
    for photo in a['images']:
        rotation=photo.get('display_rotation',0)
        bits,small=signature(primary/photo['file'],rotation)
        width,height=(photo['height'],photo['width']) if rotation in (90,270) else (photo['width'],photo['height'])
        references.append((photo,width,height,bits,small))
    # Identify each input against the complete canonical sequence first. Two
    # independently watermarked copies of the same pose are source variants,
    # not an ambiguity between two different canonical photographs.
    assigned={p['number']:[] for p in a['images']}
    for other in unique.values():
        matches=[]
        for angle in (0,90,270):
            w,h=(other['height'],other['width']) if angle else (other['width'],other['height'])
            hash_,preview=signature(alternative/other['file'],angle)
            for photo,width,height,bits,small in references:
                if abs(w/h-width/height)>.035:continue
                distance=(bits^hash_).bit_count()
                if distance>4:continue
                error=sum(ImageStat.Stat(ImageChops.difference(small,preview)).mean)/3
                if error<=10:matches.append((distance,error,photo,angle))
        match=select_match(matches)
        if match:
            _,error,photo,angle=match
            assigned[photo['number']].append((other,angle,error))
    changed=[];watermark_changes=[];images=[];out.mkdir(parents=True,exist_ok=True)
    for photo in a['images']:
        chosen=photo;folder=primary
        selected=None
        for other,angle,error in assigned[photo['number']]:
            old_file=(primary if selected is None else alternative)/chosen['file']
            relation=paired_optical_relation(
                old_file,alternative/other['file'],
                photo.get('display_rotation',0) if selected is None else selected[1],angle)
            candidate={**other,
                'visual_quality':{'method':'paired-decoded-pixel-v1',
                    'candidate_sha256':other['sha256'],
                    'compared_to_sha256':chosen['sha256'],
                    'same_photo_verified':True,
                    'confidence':'measured','relation':relation}}
            reason=replacement_reason(candidate,chosen)
            if reason:chosen=candidate;selected=(candidate,angle,error,reason)
        if selected:
            other,angle,error,reason=selected;chosen={**other,'number':photo['number']};folder=alternative
            if angle:chosen['display_rotation']=angle
            else:chosen.pop('display_rotation',None)
            (changed if reason=='measured_higher_optical_detail' else watermark_changes).append({'number':photo['number'],'source_number':other['number'],'from_sha256':photo['sha256'],
                            'to_sha256':other['sha256'],'from_pixels':[photo['width'],photo['height']],
                            'to_pixels':[other['width'],other['height']],'comparison_mean_error':round(error,3),
                            'reason':reason,'display_rotation':angle,'site_watermark_review':watermark_review(other)})
        src=folder/chosen['file'];filename=f"{photo['number']:04d}-{chosen['sha256'][:12]}"+src.suffix
        dest=out/filename;shutil.copyfile(src,dest)
        assert hashlib.sha256(dest.read_bytes()).hexdigest()==chosen['sha256']
        images.append({**chosen,'file':filename})
    result={**a,'images':images,'higher_resolution_web_replacements':changed,
            'watermark_free_web_replacements':watermark_changes,
            'quality':'public_web_measured_optical_detail','publisher_original_verified':False,
            'source_pages':list(dict.fromkeys(a.get('source_pages',[])+b.get('source_pages',[])))}
    (out/'manifest.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    print('MEASURED_HIGHER_OPTICAL_DETAIL_WEB_FILES_SELECTED',len(changed),'of',len(images),flush=True)
    print('MEASURED_COMPARABLE_VERIFIED_WATERMARK_FREE_FILES_SELECTED',len(watermark_changes),flush=True)
    return result
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('primary',type=Path);p.add_argument('alternative',type=Path);p.add_argument('out',type=Path);a=p.parse_args()
    if a.out.resolve().is_relative_to(Path(__file__).resolve().parents[2]):p.error('Use a private output outside the repository')
    merge(a.primary,a.alternative,a.out)
    from build_additional_source_manifest import build
    build([a.out],Path(__file__).with_name('additional-source-albums.json'))
