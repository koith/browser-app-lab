"""Report missing sequence members and resolution debt without claiming masters."""
import json
from pathlib import Path
from datetime import datetime,timezone
ROOT=Path(__file__).parent

def audit():
 source={}
 for name in ['source-viewer-albums.json','additional-source-albums.json']:
  for a in json.loads((ROOT/name).read_text())['albums']:source[a['id']]=a
 local=json.loads((ROOT/'stored-albums.json').read_text())['albums'];rows=[]
 aliases=json.loads((ROOT/'album-aliases.json').read_text())['aliases']
 # Local exact-hash fallback files stay on disk; duplicate work cards do not.
 visible=[*source.values(),*(a for a in local if aliases.get(a['id']) not in source)]
 for a in visible:
  images=a['images'];expected=a.get('expected');numbers=[p.get('number',i+1) for i,p in enumerate(images)];unique=len({p['sha256'] for p in images})
  missing=sorted(set(range(1,expected+1))-set(numbers)) if expected else None
  extra=sorted(set(numbers)-set(range(1,expected+1))) if expected else []
  complete=bool(not a.get('not_complete_photobook') and expected and not missing and not extra and unique==expected and len(images)==expected)
  sizes=sorted({(p['width'],p['height']) for p in images})
  rows.append({'id':a['id'],'title':a.get('title',a['id']),'acquired':len(images),'expected_web_edition':None if a.get('expected_total_unknown') else expected,'advertised_publisher_photos':a.get('advertised_publisher_photos'),'collection_kind':a.get('collection_kind'),'sequence_complete':complete,'missing_numbers':None if a.get('expected_total_unknown') else missing,'duplicate_files':len(images)-unique,'dimensions':sizes,'minimum_long_edge':min(max(p['width'],p['height']) for p in images),'publisher_master_verified':False,'highest_resolution_status':'unverified','follow_up_required':True,'reason':'public subset; publisher full edition/total coverage unverified' if a.get('not_complete_photobook') else 'public preview only; identify and acquire complete work' if a in local else 'web sequence complete; continue highest-resolution source comparison' if complete else 'missing web photos and original resolution unverified'})
 return {'checked_at':datetime.now(timezone.utc).isoformat(),'arbitrary_resolution_completion_threshold':None,'not_publisher_master_certification':True,'complete_web_albums':sum(r['sequence_complete'] for r in rows),'preview_or_incomplete_groups':sum(not r['sequence_complete'] for r in rows),'gallery_entries':sum(r['acquired'] for r in rows),'albums':rows}
if __name__=='__main__':
 report=audit();(ROOT/'verification/gallery-coverage.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n');print('GALLERY_COVERAGE_AUDIT',report['gallery_entries'],report['complete_web_albums'],report['preview_or_incomplete_groups'])
