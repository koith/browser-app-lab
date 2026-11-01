#!/usr/bin/env python3
"""Extract COMPLETE original OBS sprite frames for source-inventoried actors.

The previously checked-in animation-extra.js inventory is the whitelist,
not a name-range guess. This never invents frames, actions or actor IDs.
Only 0040/0046/0078 have reviewed left-profile and attack mapping.
Original 2002 4LEAF executable direction/action/FPS table remains unknown.

The SHA1-verified original installer must be unpacked to an unshield folder.
Every member's raw SHA256 is compared to checked-in source inventory;
each produced PNG includes an individual SHA256, size and native origin.
"""
import hashlib
import importlib.util
import json
import sys
from pathlib import Path

HERE=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('leaf_source_full',HERE/'extract-targeted-original-frames.py')
target=importlib.util.module_from_spec(spec)
sys.modules[spec.name]=target
spec.loader.exec_module(target)

REVIEWED={'0040','0046','0078'}
EXPECTED_FRAMES=37
MIN_ACTORS=40


def checked_in_inventory(root):
    file=root/'apps/4leaf/rog/original/OBS/animation-extra.js'
    text=file.read_text(encoding='utf-8')
    begin=text.index('\n{\n')+1
    end=text.rindex('\n);')
    data=json.loads(text[begin:end])
    accepted={}
    for id,rec in data.items():
        if rec.get('originalAnimationCount')!=EXPECTED_FRAMES:
            continue
        name=rec.get('originalMember','').lower()
        checksum=rec.get('sourceSHA256','')
        if not (len(id)==4 and id.isdigit() and
                name.startswith('1') and name.endswith('.obs') and
                len(checksum)==64 and
                all(c in '0123456789abcdef' for c in checksum)):
            raise ValueError('Invalid whitelisted actor source: '+id)
        if name in accepted:raise ValueError('Duplicate original member '+name)
        accepted[name]=(id,checksum)
    assert len(accepted)>=MIN_ACTORS,('source inventory unexpectedly reduced',len(accepted))
    assert REVIEWED.issubset({id for id,_ in accepted.values()})
    return accepted


def extract(resource_dir,root):
    root=Path(root)
    verified=checked_in_inventory(root)
    paths=[p for p in Path(resource_dir).rglob('*') if p.is_file() and p.name.lower()=='obs.pak']
    if len(paths)!=1: raise ValueError('Expected one original OBS.pak; found '+str(paths))
    source=paths[0].read_bytes()
    out=root/'apps/4leaf/rog/original/OBS/action-full'
    out.mkdir(parents=True,exist_ok=True)
    old_manifest=out/'manifest.js'
    prior={}
    if old_manifest.exists():
        text=old_manifest.read_text()
        if '=' in text: prior=json.loads(text.split('window.ORIGINAL_LEAF_FULL_ACTION_FRAMES=',1)[1].rsplit(';',1)[0])
    records={}
    census={'sourcePak':'OBS.pak','sourcePakSHA256':target.sha(source),
       'sourceInventoryMembers':len(verified),'originalExeActionTableDecoded':False,
       'members':{},'failures':{}}
    for name,blob in target.codec.source_members(source):
        key=name.lower()
        if key not in verified:continue
        id,expected=verified[key]
        sha=target.sha(blob)
        if sha!=expected:
            census['failures'][key]={'reason':'original member SHA256 differs from checked-in source inventory','expected':expected,'actual':sha}
            continue
        info,images,_,error=target.decode_member(blob)
        if error or len(info)!=EXPECTED_FRAMES or len(images)!=EXPECTED_FRAMES:
            census['failures'][key]={'reason':error or 'missing decoded frames',
                'declared':len(info),'decoded':len(images)}
            continue
        frames=[]
        stem=Path(name).stem
        for f in info:
            i=f['index']
            if i not in images:raise ValueError('Missing frame '+name+':'+str(i))
            binary=target.png_bytes(images[i])
            filename=f'{stem}-{i:02d}.png'
            where=out/filename
            if id in REVIEWED and where.exists():
                old_sha=target.sha(where.read_bytes())
                if old_sha!=target.sha(binary):
                    raise ValueError('Existing manually reviewed original pixels changed '+filename)
            where.write_bytes(binary)
            frames.append({'index':i,'url':'./original/OBS/action-full/'+filename,
              'width':f['width'],'height':f['height'],
              'originX':f['originX'],'originY':f['originY'],
              'sha256':target.sha(binary)})
        records[id]={'sourcePak':'OBS.pak','originalMember':name,
            'sourceSHA256':sha,'originalAnimationCount':EXPECTED_FRAMES,
            'hasVerifiedFrameZero':True,
            'poseMapping':('37 ORIGINAL PIXEL FRAMES; reviewed left-profile 14-17 and weapon poses 31/33/35; WEB action timing INFERRED'
              if id in REVIEWED else '37 ORIGINAL PIXEL FRAMES; source role inventoried; full direction/action mapping UNVERIFIED'),
            'frames':frames}
        census['members'][id]={'name':name,'sourceSHA256':sha,
             'sourceFrameCount':EXPECTED_FRAMES,
             'rendererDirectionReview':'visual-reviewed-20261101' if id in REVIEWED else 'UNVERIFIED'}
    missing=set(verified)-{v['name'].lower() for v in census['members'].values()}
    for name in missing:
        if name not in census['failures']:
            census['failures'][name]={'reason':'original source member not found'}
    if len(records)<MIN_ACTORS or not REVIEWED.issubset(records):
        raise ValueError('Critical original source inventory missing or decode failed: '+
                         json.dumps(census['failures'],sort_keys=True))
    census['actorCount']=len(records)
    census['totalFrames']=sum(len(x['frames']) for x in records.values())
    census['manuallyReviewedDirectionActorCount']=len(REVIEWED)
    (out/'manifest.js').write_text(
      '/* SHA-verified original 2002 Dice/OBS.pak 37-frame actor source.\n'
      ' * Only 0040/0046/0078 have manually reviewed side/weapon pose attribution.\n'
      ' * The original EXE action table, true FPS and other directions remain UNVERIFIED. */\n'
      'window.ORIGINAL_LEAF_FULL_ACTION_FRAMES='+
      json.dumps(records,indent=1,sort_keys=True)+';\n',encoding='utf-8')
    (out/'provenance.json').write_text(json.dumps(census,indent=2,sort_keys=True)+'\n')
    return census


if __name__=='__main__':
    if len(sys.argv)!=3:
        raise SystemExit('usage: extract-reviewed-actor-complete.py resources repo_root')
    report=extract(Path(sys.argv[1]),Path(sys.argv[2]))
    print('4LEAF_COMPLETE_ORIGINAL_ACTOR_CENSUS',json.dumps({
      'sourceInventory':report['sourceInventoryMembers'],
      'actors':report['actorCount'],'frames':report['totalFrames'],
      'directionReviewedActors':report['manuallyReviewedDirectionActorCount'],
      'failures':report['failures']},sort_keys=True))
