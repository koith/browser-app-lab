#!/usr/bin/env python3
"""Preserve only manually inspected, complete 37-frame Genesis chessmen.

Authentic 2002 Dice/OBS.pak source pixels, SHA1-verified client provenance.
The exact EXE direction, action and animation-timing tables remain UNKNOWN.
This extractor never executes original Windows code or invents sprite frames.
"""
import importlib.util
import json
import sys
from pathlib import Path

HERE=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('leaf_source_full',HERE/'extract-targeted-original-frames.py')
target=importlib.util.module_from_spec(spec)
sys.modules[spec.name]=target
spec.loader.exec_module(target)

# Full source pose contact sheets reviewed upright: left-facing walking
# silhouettes around frames 14-17, original 0-8 rear and 25-30 front.
# This is SOURCE PIXEL verification, not a recovered source EXE action table.
REVIEWED={'1040.obs':'0040','1046.obs':'0046','1078.obs':'0078'}

def extract(resource_dir,root):
    paths=[p for p in Path(resource_dir).rglob('*') if p.is_file() and p.name.lower()=='obs.pak']
    if len(paths)!=1: raise ValueError('Expected one original OBS.pak; found '+str(paths))
    out=Path(root)/'apps/4leaf/rog/original/OBS/action-full'
    out.mkdir(parents=True,exist_ok=True)
    reviewed={}
    for name,blob in target.codec.source_members(paths[0].read_bytes()):
        key=name.lower()
        if key not in REVIEWED: continue
        info,images,_,error=target.decode_member(blob)
        if error or len(info)!=37 or len(images)!=37:
            raise ValueError('Bad original 37-frame member '+name+' '+str(error))
        frames=[]
        stem=Path(name).stem
        for f in info:
            i=f['index']
            if i not in images: raise ValueError('Missing '+name+': '+str(i))
            binary=target.png_bytes(images[i])
            filename=f'{stem}-{i:02d}.png'
            (out/filename).write_bytes(binary)
            frames.append({'index':i,'url':'./original/OBS/action-full/'+filename,
              'width':f['width'],'height':f['height'],
              'originX':f['originX'],'originY':f['originY'],
              'sha256':target.sha(binary)})
        reviewed[REVIEWED[key]]={'sourcePak':'OBS.pak','originalMember':name,
          'sourceSHA256':target.sha(blob),'originalAnimationCount':37,
          'hasVerifiedFrameZero':True,'poseMapping':
            'full original indexed 2D pixels; 14-17 left profile visually reviewed, original playback timing inferred',
          'frames':frames}
    if set(reviewed)!=set(REVIEWED.values()):
        raise ValueError('Missing source actors '+str(set(REVIEWED.values())-set(reviewed)))
    (out/'manifest.js').write_text(
      '/* 2002 original OBS.pak complete 37-frame source sprites.\n'
      ' * Historic EXE action/direction mapping NOT decoded; source images only. */\n'
      'window.ORIGINAL_LEAF_FULL_ACTION_FRAMES='+
      json.dumps(reviewed,indent=1,sort_keys=True)+';\n')
    (out/'provenance.json').write_text(json.dumps({
      'sourcePakSHA256':target.sha(paths[0].read_bytes()),
      'actorCount':len(reviewed),
      'totalFrames':sum(len(a['frames']) for a in reviewed.values()),
      'members':{k:{'name':v['originalMember'],'sha256':v['sourceSHA256']}
                 for k,v in reviewed.items()},
      'originalExeActionTableDecoded':False,
      'review':'per-frame source body angle verified visually, action FPS and direction control INFERRED'
    },indent=2)+'\n')
    return reviewed

if __name__=='__main__':
    if len(sys.argv)!=3: raise SystemExit('usage: extract-reviewed-actor-complete.py resources repo_root')
    found=extract(Path(sys.argv[1]),Path(sys.argv[2]))
    print('4LEAF_FULL_ORIGINAL_ACTIONS',json.dumps({k:len(v['frames']) for k,v in found.items()}))
