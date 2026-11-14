'use strict';
const assert=require('node:assert/strict');
const run=require('./gallery_event_handoff.cjs');
const SHA='a'.repeat(40);
const ledger=(done=[1,2,4])=>Array.from({length:11},(_,i)=>
  '- ['+(done.includes(i+1)?'x':' ')+'] **G-'+String(i+1).padStart(2,'0')+'** work').join('\n');
// Reproduce #605's LIVE 2026-11-11 dashboard table: completed subtasks
// inside an incomplete G-03 must not count as top-level completion.
const tableLedger=(done=[1,2,4])=>'<!-- GALLERY_DASHBOARD_START -->\n'+
  '# 화보 갤러리 — 실제 개발 원장\n'+
  Array.from({length:11},(_,i)=>{
    const n=i+1,id='G-'+String(n).padStart(2,'0');
    const status=done.includes(n)?'[x]':'[ ]';
    const desc=n===3?'[x] 밈미 신규 2장 실화면 완료 · 전체 수집은 [ ]':'보관·실증';
    return '| '+(done.includes(n)?'완료':'P0')+' | '+id+
      ' | '+desc+' | '+status+' 전체 작업 '+(n===3?'새 2장 [x]':'')+' |';
  }).join('\n')+
  '\n<!-- GALLERY_DASHBOARD_END -->\n'+
  '\n## Old history: must NEVER overwrite current dashboard status\n'+
  '- [x] **G-10** old entry\n';
// 2026-11-14: exactly 10 finite G-IDs plus two non-terminating collectors.
const modernLedger=(done=[1,2,4,5,6,7,8,9,10,11])=>{
  const finite=[1,2,4,5,6,7,8,9,10,11];
  const rows=finite.map(n=>{
    const id='G-'+String(n).padStart(2,'0');
    return '| 완료형 | '+id+' | 실제 기능 | '+(done.includes(n)?'[x]':'[ ]')+' 수용 |';
  });
  rows.push('| 무기한 반복 | G-03 | 밈미 신규 수집 | ↻ 상시 |');
  rows.push('| 무기한 반복 | G-12 | 심유이 신규 수집 | ↻ 상시 |');
  return '<!-- GALLERY_DASHBOARD_START -->\n'+
    '## 2026-11-14 최신 유한 원장\n'+
    '## 유한 개발 / 상시 수집 — 최신 상태판\n'+
    '| 구분 | ID | 범위 | 판정 |\n'+rows.join('\n')+
    '\n## 자율개발 기준\n'+
    '| P0 | G-03 | 구형 체크 | [ ] 예전 미완료 |\n'+
    '| P0 | G-11 | 구형 체크 | [ ] 예전 미완료 |\n'+
    '<!-- GALLERY_DASHBOARD_END -->';
};
const item=(status='completed',conclusion='success',sha=SHA)=>({
  id:42,head_sha:sha,head_branch:'main',status,conclusion,event:'workflow_dispatch'
});
async function simulate({event='push',body=ledger(),history={},pages=[item()],
  payload,ref='refs/heads/main',galleryTreesEqual=false,graphQlFails=false}={}) {
  const dispatched=[],logs=[];
  const p=payload||(event==='push'
    ?{repository:{full_name:'koith/browser-app-lab'}}
    :event==='issues'?{action:'edited',issue:{number:605}}
    :{action:'completed',workflow_run:{
      name:'Deploy static content to Pages',head_branch:'main',
      head_repository:{full_name:'koith/browser-app-lab'},event:'push'}});
  const github={
    graphql:async query=>{
      if(graphQlFails)throw new Error('GRAPHQL_TEMPORARY_UNAVAILABLE');
      assert.match(query,/sourceMimmi: object/);
      const result={};
      for(const [i,name] of ['Mimmi','Yui','Archive'].entries()) {
        result['source'+name]={oid:String(i+1).repeat(40)};
        result['published'+name]={oid:String(i+1+(galleryTreesEqual?0:1)).repeat(40)};
      }
      return {repository:result};
    },
    rest:{
    issues:{get:async()=>({data:{body}})},
    git:{getRef:async()=>({data:{object:{sha:SHA}}})},
    actions:{
      listWorkflowRuns:async({workflow_id})=>({data:{
        workflow_runs:workflow_id==='static.yml'?pages:(history[workflow_id]||[])
      }}),
      createWorkflowDispatch:async x=>{dispatched.push(x.workflow_id);}
    }
  }};
  await run({github,context:{repo:{owner:'koith',repo:'browser-app-lab'},
    eventName:event,ref,payload:p},
    core:{info:x=>logs.push(x),notice:x=>logs.push(x),warning:x=>logs.push(x)}});
  return {dispatched,logs};
}
(async()=>{
  const g10='gallery-quality-branding-entry-qa.yml';
  const g09='gallery-first-image-metrics.yml';
  const g11='gallery-deployed-pages-photo-qa.yml';
  const g08='gallery-visual-quality-audit.yml';
  let r=await simulate();
  assert.deepEqual(r.dispatched,[g10],'cheap branding QA first');
  r=await simulate({pages:[item('in_progress',null)]});
  assert.deepEqual(r.dispatched,[],'wait for actual deployment');
  r=await simulate({pages:[item('completed','failure')]});
  assert.deepEqual(r.dispatched,[],'failed deployment never starts feature QA');
  r=await simulate({history:{[g10]:[item('in_progress',null)]}});
  assert.deepEqual(r.dispatched,[],'avoid duplicate active QA');
  r=await simulate({history:{[g10]:[item()]}});
  assert.deepEqual(r.dispatched,[g09],
    'a completed G10 check at this SHA must unblock independent G09 QA');
  r=await simulate({history:{[g10]:[item()],[g09]:[item()]}});
  assert.deepEqual(r.dispatched,[g11],
    'a blocked but already attempted G09 must not halt mobile QA');
  r=await simulate({history:{[g10]:[item()],[g09]:[item('queued',null)]}});
  assert.deepEqual(r.dispatched,[],'inflight stage blocks premature parallel QA');
  r=await simulate({history:{[g10]:[item()],[g09]:[item()],
                             [g11]:[item()]}});
  assert.deepEqual(r.dispatched,[g08],'optical feature audit continues independently');
  r=await simulate({history:{[g10]:[item()],[g09]:[item()],
                             [g11]:[item()],[g08]:[item()]}});
  assert.deepEqual(r.dispatched,[],'no infinite retries on unchanged SHA');
  r=await simulate({event:'issues',body:ledger([1,2,4,10])});
  assert.deepEqual(r.dispatched,[g09],'checked branding stage is skipped');
  r=await simulate({event:'issues',body:ledger([1,2,4,9,10,11])});
  assert.deepEqual(r.dispatched,[g08],'only unfinished quality audit remains');
  r=await simulate({body:ledger([1,2,4,8,9,10,11])});
  assert.deepEqual(r.dispatched,[],'all feature issues complete');
  r=await simulate({event:'workflow_run',payload:{action:'completed',workflow_run:{
    name:'Deploy static content to Pages',head_branch:'main',
    head_repository:{full_name:'evil/fork'},event:'push'}}});
  assert.deepEqual(r.dispatched,[],'untrusted source never dispatches');
  for(const name of ['gallery-direct-individual-archive.yml',
    'gallery-targeted-public-photo-crawl.yml','mimmi-official-archive.yml'])
    assert.ok(!r.dispatched.includes(name),'collection stays paused');
  r=await simulate({body:tableLedger()});
  assert.deepEqual(r.dispatched,[g10],
    'real dashboard table should be read instead of blocking handoff');
  assert.ok(r.logs.some(x=>x.includes('GALLERY_DASHBOARD_PARSED_DONE 3/11')),
    'global task count must stay 3/11 despite G03 two-photo subtask being done');
  r=await simulate({body:tableLedger([1,2,4,10])});
  assert.deepEqual(r.dispatched,[g09],'table-form completed G10 advances to G09');
  r=await simulate({body:tableLedger([1,2,4,9,10,11])});
  assert.deepEqual(r.dispatched,[g08],'table-form G08 remains separately actionable');
  r=await simulate({body:tableLedger([1,2,4,8,9,10,11])});
  assert.deepEqual(r.dispatched,[],'fully completed feature rows must not re-run');
  r=await simulate({body:tableLedger().replace('| G-11 |','| OTHER |')});
  assert.deepEqual(r.dispatched,[],
    'missing critical global row must fail closed, not dispatch unknown work');
  const oldPublished='b'.repeat(40);
  r=await simulate({pages:[item('completed','success',oldPublished)],
                    galleryTreesEqual:true});
  assert.deepEqual(r.dispatched,[g10],
    'same gallery tree OIDs should unlock QA despite unrelated monorepo commits');
  assert.ok(r.logs.some(x=>x.includes('GALLERY_PAGES_TREE_EQUIVALENT')));
  r=await simulate({pages:[item('completed','success',oldPublished)],
                    galleryTreesEqual:false});
  assert.deepEqual(r.dispatched,[],
    'changed gallery tree must require an actual new Pages deployment');
  r=await simulate({pages:[item('completed','success',oldPublished)],
                    galleryTreesEqual:true,graphQlFails:true});
  assert.deepEqual(r.dispatched,[],
    'GitHub tree identity request failure cannot imply same Pages');
  r=await simulate({pages:[item('in_progress',null),
                    item('completed','success',oldPublished)],galleryTreesEqual:true});
  assert.deepEqual(r.dispatched,[],
    'an exact-source deploy in progress must not be bypassed by old Pages');
  r=await simulate({pages:[{...item('completed','success',oldPublished),
                    head_branch:'dev'}],galleryTreesEqual:true});
  assert.deepEqual(r.dispatched,[],
    'non-main Pages success may not authorize gallery QA');
  // Modern finite completion must not depend on either perpetual collector.
  r=await simulate({body:modernLedger()});
  assert.deepEqual(r.dispatched,[], '10/10 finite done: no phantom QA dispatch');
  assert.ok(r.logs.some(x=>x.includes('GALLERY_FINITE_DASHBOARD_PARSED_DONE 10/10 PERPETUAL G-03,G-12')));
  assert.ok(r.logs.some(x=>x.includes('FINITE_FEATURES_COMPLETE_PERPETUAL_COLLECTION_ACTIVE')));
  r=await simulate({body:modernLedger([1,2,4,5,6,7,8,9,10])});
  assert.deepEqual(r.dispatched,[g11], 'a real unfinished finite G11 still triggers QA');
  r=await simulate({body:modernLedger().replace('| G-12 |','| BAD |')});
  assert.deepEqual(r.dispatched,[], 'missing Yui perpetual contract fails closed');
  assert.ok(r.logs.some(x=>x.includes('BLOCK_MISSING_PERPETUAL_COLLECTION G-12')));
  r=await simulate({body:modernLedger().replace('| G-05 |','| BAD |')});
  assert.deepEqual(r.dispatched,[], 'missing finite contract fails closed');
  assert.ok(r.logs.some(x=>x.includes('BLOCK_MISSING_FINITE_LEDGER G-05')));
  console.log('PASS: legacy 13 + table-first 5 + gallery-tree parity 5 + perpetual finite 4 handoff cases');
})().catch(e=>{console.error(e);process.exitCode=1;});
