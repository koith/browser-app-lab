#!/usr/bin/env python3
"""Connect actual downloaded public Chinese previews to the album-first gallery.

Input is downloaded and SHA256-verified by archive_engine.py.
Never create a gallery record without a local file and matching hash.
"""
from pathlib import Path
from hashlib import sha256
import json,shutil,time
ROOT=Path("apps/yui-gallery")
IN=Path("yui-dynamic-images")
OUT=ROOT/"stored-albums"
ALBUMS=ROOT/"albums.json"
STORED=ROOT/"stored-albums.json"
METADATA={
"huantuji-yui-collection":("cn-huantuji","幻图集","Yui · 공개 미리보기 (화보 미분류)"),
"chaotuji-yui-collection":("cn-chaotuji","潮图集","Yui · 공개 미리보기 (화보 미분류)"),
"miaohuaying-yui-collection":("cn-miaohuaying","喵画影","Yui · 공개 미리보기 (화보 미분류)"),
"yuntu8-yui-profile":("cn-yuntu8","云图吧","沈惠星 Yui · 공개 사진 미리보기"),
"wantuzhi-everyday-life":("cn-wantuzhi-everyday","玩图志","Yui — Everyday Life (공개 미리보기)"),
"yingyuge-yui-collection":("cn-yingyuge","影语阁","沈惠星 Yui · 공개 미리보기 (화보 미분류)")
}
db=json.loads(ALBUMS.read_text(encoding="utf-8"))
old=json.loads(STORED.read_text(encoding="utf-8")) if STORED.exists() else {"albums":[]}
byid={a['id']:a for a in old['albums']}
known={a['id'] for a in db['albums']}
new_count=0
for src,(aid,site,title) in METADATA.items():
 folder=IN/src
 manifest=folder/"manifest.json"
 if not manifest.is_file():
  print("MISSING_SOURCE",src,flush=True)
  continue
 source=json.loads(manifest.read_text(encoding="utf-8"))
 files=[]
 for item in source.get("downloaded",[]):
  if item.get("status")!="downloaded":continue
  rel=Path(item["local_path"])
  f=IN/rel
  if not f.is_file():continue
  raw=f.read_bytes()
  digest=sha256(raw).hexdigest()
  if digest!=item["sha256"]:raise ValueError(f"Checksum differs for {f}")
  dst=OUT/aid/f.name
  dst.parent.mkdir(parents=True,exist_ok=True)
  if not dst.exists():dst.write_bytes(raw)
  files.append({
   "url":f"stored-albums/{aid}/{f.name}",
   "source_url":item["url"],"origin_page":item["origin_page"],
   "sha256":digest,"width":item["width"],"height":item["height"],"bytes":len(raw)
  })
 if not files:continue
 new_count+=len(files)
 old_files={p["sha256"]:p for p in byid.get(aid,{}).get("images",[])}
 for entry in files:old_files[entry["sha256"]]=entry
 byid[aid]={"id":aid,"title":title,"site":site,"source":source["source"],
  "expected":source.get("summary",{}).get("declared_photos"),
  "images":list(old_files.values()),"status":"public_previews_only_not_complete",
  "pages_visited":len(source.get("pages",[])),"errors":source.get("failed",[])}
 if aid not in known:
  db["albums"].append({"id":aid,"site":site,"title":title,
   "photos":None,"source":source["source"],"kind":"local-preview",
   "sourceUpdatedAt":time.strftime("%Y-%m-%d",time.gmtime())})
  known.add(aid)
 print("STORED_SOURCE",aid,len(files),"actual image files",flush=True)
db["updated"]=time.strftime("%Y-%m-%d",time.gmtime())
ALBUMS.write_text(json.dumps(db,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
STORED.write_text(json.dumps({"updated":time.strftime("%Y-%m-%dT%H:%M:%SZ",time.gmtime()),
 "storage":"physically stored public previews in GitHub Pages repository, not paid originals",
 "albums":list(byid.values())},ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
if new_count<5:raise RuntimeError(f"Only {new_count} actual files, refusing archive success")
print("ACTUAL_STORED_PREVIEW_FILES",new_count,flush=True)
