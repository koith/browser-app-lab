'use strict';
/* A bookkeeping acceptance only: original 2002 game fidelity is not proved
 * by mapping historical FL-01..16 work labels onto this modern task ledger. */
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const root=path.resolve(__dirname,'..');
const doc=fs.readFileSync(path.join(root,'docs/FL_WORKSTREAM_RECONCILIATION_2026-10-20.md'),'utf8');
const ledger=JSON.parse(fs.readFileSync(path.join(root,'docs/RESTORATION_LEDGER.json'),'utf8'));
const taskIds=new Set(ledger.tasks.map(task=>task.id));
assert.equal(taskIds.size,ledger.tasks.length,'duplicate ledger task IDs');
assert.ok(taskIds.size>=60,'preserve original 60 tasks, never shrink the canonical backlog');
const rows=doc.split(/\r?\n/).filter(line=>/^\|\s*\*\*FL-\d{2}\*\*\s*\|/.test(line));
assert.equal(rows.length,16,'exactly 16 historical FL workstream titles');
const covered=new Set();
for(let n=1;n<=16;n++){
 const label='FL-'+String(n).padStart(2,'0');
 const matches=rows.filter(row=>row.includes('**'+label+'**'));
 assert.equal(matches.length,1,label+' must map to exactly one source title');
 const columns=matches[0].split('|');
 assert.ok(columns[2]?.trim(),'do not replace original FL title with generic placeholder');
 const ids=[...String(columns[4]||'').matchAll(/`([A-Z][A-Z0-9-]+)`/g)].map(x=>x[1]);
 assert.ok(ids.length>0,label+' has no canonical task linkage');
 for(const id of ids){assert.ok(taskIds.has(id),label+' references missing task '+id);covered.add(id);}
 if(n>=13)assert.ok(matches[0].includes('상태 표기 회수 불가'),
  'never fabricate unrecovered earlier FL-'+n+' completion state');
}
for(const id of ['M00','SRC-01','SRC-02','SRC-04','BRD-04','ACT-05']){
 assert.ok(doc.includes('`'+id+'`'),'shared upstream task not reconciled: '+id);
}
const mentioned=new Set([...doc.matchAll(/`([A-Z][A-Z0-9-]+)`/g)].map(m=>m[1]));
const missing=[...taskIds].filter(id=>!mentioned.has(id));
assert.deepEqual(missing,[],'canonical ledger IDs omitted from FL reconciliation evidence');
assert.match(doc,/원작 게임의 남은 구현·원본 비교 작업은 계속 미완료/,
 'do not equate a verified mapping with completed historical game reproduction');
console.log('4LEAF_FL_WORKSTREAM_RECONCILIATION_PASS',
 JSON.stringify({fl:rows.length,canonical:taskIds.size,explicitLinked:covered.size,
 shared:['M00','SRC-01','SRC-02','SRC-04','BRD-04','ACT-05'],missing:missing.length}));
