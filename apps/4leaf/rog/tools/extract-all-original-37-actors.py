#!/usr/bin/env python3
"""Extract full ORIGINAL 37-frame OBS actor packets for every authenticated
2002 Genesis chessman source ID in existing checked-in archival manifests.
No action semantics are invented; PNGs retain original palette and origin.
"""
from __future__ import annotations
import importlib.util
import json
import sys
from pathlib import Path

HERE=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('leaf37_source',HERE/'extract-targeted-original-frames.py')
source=importlib.util.module_from_spec(spec)
sys.modules[spec.name]=source
spec.loader.exec_module(source)

def parse_js_json(path,marker):
    text=path.read_text()
    start=text.index(marker)+len(marker)
    tail=text[start:]
    # The extra manifest's JSON is the first brace following Object.assign(
    # and the legacy manifest's JSON follows '=' directly.
    # Object.assign(window.OLD||{}, {REAL MAP}) contains an empty
    # fallback '{}' BEFORE the map. Select the standalone brace on its
    # own line, not the empty fallback object.
    first=tail.index('\\n{')+1 if 'Object.assign(' in marker else tail.index('{')
    obj,_=json.JSONDecoder().raw_decode(tail[first:])
    return obj

def expected_actors(root):
    base=Path(root)/'apps/4leaf/rog/original/OBS'
    extra=parse_js_json(base/'animation-extra.js','window.ORIGINAL_LEAF_OBS_FRAMES=Object.assign(')
    base_map=parse_js_json(base/'animation-manifest.js','window.ORIGINAL_LEAF_OBS_FRAMES=')
    ids={}
    for key,record in {**extra,**base_map}.items():
        if record.get('sourcePak')!='OBS.pak' or record.get('originalAnimationCount')!=37:
            continue
        member=record.get('originalMember','').lower()
        if not (len(key)==4 and key.isdecimal() and member.endswith('.obs')):
            raise ValueError('Bad verified source identity '+key)
        ids[member]=(key,record.get('sourceSHA256'))
    if len(ids)!=47:
        raise ValueError('Expected 47 existing documented 37-frame source actors; got '+str(len(ids)))
    return ids

def extract(resource_dir,root):
    root=Path(root)
    match=[p for p in Path(resource_dir).rglob('*') if p.is_file() and p.name.lower()=='obs.pak']
    if len(match)!=1:raise ValueError('Exactly one original OBS.pak required')
    allow=expected_actors(root)
    dest=root/'apps/4leaf/rog/original/OBS/action-full'
    dest.mkdir(parents=True,exist_ok=True)
    existing={}
    manifest_path=dest/'manifest.js'
    if manifest_path.exists():
        existing=parse_js_json(manifest_path,'window.ORIGINAL_LEAF_FULL_ACTION_FRAMES=')
    result={}
    for name,raw in source.codec.source_members(match[0].read_bytes()):
        id_and_sha=allow.get(name.lower())
        if id_and_sha is None:continue
        chess_id,previous_sha=id_and_sha
        digest=source.sha(raw)
        if previous_sha is not None and digest!=previous_sha:
            raise ValueError('Original checksum mismatch for '+name+'; old '+str(previous_sha)+' new '+digest)
        if chess_id in existing and existing[chess_id].get('sourceSHA256')!=digest:
            raise ValueError('Existing extracted actor has conflicting original bytes '+chess_id)
        records,imgs,_,error=source.decode_member(raw)
        if error or len(records)!=37 or len(imgs)!=37:
            raise ValueError('Bad full original source actor '+name+': '+str(error))
        frames=[]
        for rec in records:
            i=rec['index']
            if i not in imgs:raise ValueError('Original frame absent '+name+' '+str(i))
            png=source.png_bytes(imgs[i])
            filename=Path(name).stem+f'-{i:02d}.png'
            destination=dest/filename
            if destination.exists() and destination.read_bytes()!=png:
                raise ValueError('Previously reviewed original PNG differs '+filename)
            destination.write_bytes(png)
            frames.append({'index':i,'url':'./original/OBS/action-full/'+filename,
                'width':rec['width'],'height':rec['height'],
                'originX':rec['originX'],'originY':rec['originY'],
                'sha256':source.sha(png)})
        result[chess_id]={'sourcePak':'OBS.pak','originalMember':name,
          'sourceSHA256':digest,'originalAnimationCount':37,
          'hasVerifiedFrameZero':True,
          'poseMapping':'authentic 37 frames, source orientations partially reviewed; WEB action timing inferred, EXE action lookup unknown',
          'frames':frames}
    if set(result)!=set(v[0] for v in allow.values()):
        raise ValueError('Missing original actor IDs '+str(set(v[0] for v in allow.values())-set(result)))
    js='/* Full SHA-verified 2002 4LEAF Dice/OBS.pak 37-frame source actor sprites.\n'+(
        ' * Historical EXE action-to-frame and 8-direction tables NOT decoded. */\n')
    js+='window.ORIGINAL_LEAF_FULL_ACTION_FRAMES='+json.dumps(result,indent=1,sort_keys=True)+';\n'
    (dest/'manifest.js').write_text(js)
    summary={'actorCount':len(result),'frames':sum(len(v['frames']) for v in result.values()),
      'archiveObsPakSHA256':source.sha(match[0].read_bytes()),
      'members':{k:{'member':v['originalMember'],'sha256':v['sourceSHA256']} for k,v in result.items()},
      'originalExeActionTableDecoded':False,
      'note':'Complete original 2D frames only; historical behavior and rate are inferred and not claimed verified'}
    (dest/'provenance.json').write_text(json.dumps(summary,indent=2)+'\n')
    return summary

if __name__=='__main__':
    if len(sys.argv)!=3:raise SystemExit('usage: extract-all-original-37-actors.py original_resources repo_root')
    print('ALL_47_SOURCE_ACTORS',json.dumps(extract(sys.argv[1],sys.argv[2]),sort_keys=True)[:3000])
