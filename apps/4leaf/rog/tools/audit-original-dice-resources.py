#!/usr/bin/env python3
"""SHA-grounded read-only Dice resource inventory from verified 2002 archive.

Identify real source candidates for raised battle podiums, falling D4/D6
models, animations and camera MVE before any invented mesh replacement.
No binary execution, no asset reclassification based solely on filenames.
"""
import hashlib, json, os, struct, sys
from pathlib import Path

def pak_members(data):
    if len(data)<32:return []
    count=struct.unpack_from('<I',data,0)[0]^0xffffffff
    if not 1<=count<=10000:return []
    start=4+count*28
    if start>=len(data):return []
    last=0; entries=[]
    for i in range(count):
        item=data[4+i*28:4+(i+1)*28]
        if len(item)!=28:return []
        name=bytes(v^255 for v in item[:24]).split(b'\0')[0].decode('cp949','replace')
        end=(struct.unpack_from('<I',item,24)[0]^0xffffffff)+1
        if end<=last or start+end>len(data):return []
        content=data[start+last:start+end]
        entries.append({'name':name,'bytes':len(content),
          'sha256':hashlib.sha256(content).hexdigest(),
          'first16':content[:16].hex()})
        last=end
    return entries if start+last==len(data) else []

def main():
    if len(sys.argv)!=3:
        raise SystemExit('Usage: audit-original-dice-resources.py extracted_resources output.json')
    source=Path(sys.argv[1]);target=Path(sys.argv[2])
    paths=[p for p in source.rglob('*') if p.is_file()
           and ('dice' in [v.lower() for v in p.parts] or 'dice' in p.name.lower())]
    results=[]
    for path in sorted(paths):
        if path.stat().st_size>100*1024*1024:continue
        raw=path.read_bytes()
        rel=path.relative_to(source).as_posix()
        members=pak_members(raw) if path.suffix.lower()=='.pak' else []
        extensions={}
        for a in members:
            ext=Path(a['name']).suffix.lower() or '(none)'
            extensions[ext]=extensions.get(ext,0)+1
        results.append({'path':rel,'bytes':len(raw),
           'sha256':hashlib.sha256(raw).hexdigest(),
           'container':bool(members),
           'memberCount':len(members),
           'extensions':extensions,'members':members[:2000]})
    evidence={'version':'source-index-2002','unverifiedGraphicsRole':True,
              'files':results,'summary':{
               'archiveCount':len(results),
               'totalEntries':sum(x['memberCount'] for x in results),
               'names':[x['path'] for x in results]}}
    target.parent.mkdir(parents=True,exist_ok=True)
    target.write_text(json.dumps(evidence,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print('ORIGINAL_DICE_SOURCE_PACKAGES '+json.dumps(evidence['summary'],ensure_ascii=False))
    for p in results:
        candidate=[m['name'] for m in p['members'] if any(
         keyword in m['name'].lower() for keyword in (
          'dice','roll','battle','stage','floor','move','war','effect','shadow','win','loss','stand'))]
        print('ORIGINAL_DICE_SOURCE_MEMBERS '+json.dumps({
          'package':p['path'],'count':p['memberCount'],
          'extensions':p['extensions'],'possibleRelevantNames':candidate[:100],
          'allNames': [m['name'] for m in p['members'][:220]]
        },ensure_ascii=False))
if __name__=='__main__':main()
