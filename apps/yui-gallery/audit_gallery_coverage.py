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
 for a in [*source.values(),*local]:
  images=a['images'];expected=a.get('expected');numbers=[p.get('number',i+1) for i,p in enumerate(images)];unique=len({p['sha256'] for p in images})
  missing=sorted(set(range(1,expected+1))-set(numbers)) if expected else None
  extra=sorted(set(numbers)-set(range(1,expected+1))) if expected else []
  complete=bool(expected and not missing and not extra and unique==expected and len(images)==expected)
  low=[numbers[i] for i,p in enumerate(images) if max(p['width'],p['height'])<1920]
  rows.append({'id':a['id'],'title':a.get('title',a['id']),'acquired':len(images),'expected_web_edition':expected,'sequence_complete':complete,'missing_numbers':missing,'duplicate_files':len(images)-unique,'below_1920_long_edge':low,'minimum_long_edge':min(max(p['width'],p['height']) for p in images),'publisher_master_verified':False,'follow_up_required':not complete or bool(low),'reason':'public preview only' if a in local else 'web edition; seek larger independent editions' if low else 'web edition; publisher master unverified'})
 return {'checked_at':datetime.now(timezone.utc).isoformat(),'resolution_review_long_edge':1920,'not_publisher_master_certification':True,'complete_web_albums':sum(r['sequence_complete'] for r in rows),'preview_or_incomplete_groups':sum(not r['sequence_complete'] for r in rows),'gallery_entries':sum(r['acquired'] for r in rows),'albums':rows}
if __name__=='__main__':
 report=audit();(ROOT/'verification/gallery-coverage.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n');print('GALLERY_COVERAGE_AUDIT',report['gallery_entries'],report['complete_web_albums'],report['preview_or_incomplete_groups'])
