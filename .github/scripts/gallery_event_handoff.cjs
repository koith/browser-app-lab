'use strict';

// #605: finite-feature handoff and independently scheduled perpetual collection.
// G-03 Mimmi and G-12 Yui are ongoing acquisition, never finite blockers.
// Actual acquisition happens in the existing hourly autonomous collector.
// A busy monorepo often supersedes Pages for unrelated apps. Reuse a
// successfully published Pages revision ONLY when all gallery subtrees have
// identical Git tree OIDs; the stronger real image/browser checks stay intact.
// One lightweight GraphQL query returns six tree identities (no file download).
async function samePublishedGalleryTrees(github,owner,repo,source,published) {
  if(!/^[a-f0-9]{40}$/.test(source)||!/^[a-f0-9]{40}$/.test(published))
    return false;
  const dirs=[
    ['Mimmi','apps/mimmi-gallery'],
    ['Yui','apps/yui-gallery'],
    ['Archive','apps/gallery-archive']
  ];
  const fields=dirs.flatMap(([label,path])=>[
    'source'+label+': object(expression:"'+source+':'+path+'") { ... on Tree { oid } }',
    'published'+label+': object(expression:"'+published+':'+path+'") { ... on Tree { oid } }'
  ]).join('\n');
  const query='query($owner:String!,$repo:String!){repository(owner:$owner,name:$repo){'+fields+'}}';
  const result=await github.graphql(query,{owner,repo});
  const trees=result?.repository;
  return !!trees && dirs.every(([label])=>{
    const a=trees['source'+label]?.oid, b=trees['published'+label]?.oid;
    return typeof a==='string'&&/^[a-f0-9]{40}$/.test(a)&&a===b;
  });
}

module.exports = async function featureHandoff({github, context, core}) {
  const owner=context.repo.owner, repo=context.repo.repo;
  const full=owner+'/'+repo, ev=context.eventName, p=context.payload;
  // Cheap independent feature checks first. A blocked G-09 must not halt G-10/G-11.
  const featureStages=[
    {id:'G-10',wf:'gallery-quality-branding-entry-qa.yml',
      name:'Gallery Quality Branding and Fast Entry Regression QA'},
    {id:'G-09',wf:'gallery-first-image-metrics.yml',
      name:'Gallery — First Image Latency and Full SHA Coverage'},
    {id:'G-11',wf:'gallery-deployed-pages-photo-qa.yml',
      name:'Yui Mimmi Deployed GitHub Pages Real Photo Browser QA'},
    {id:'G-08',wf:'gallery-visual-quality-audit.yml',
      name:'Gallery Real Image Pixel Quality Audit'},
  ];
  const deployment='Deploy static content to Pages';
  const log=msg=>{core.info('GALLERY_FEATURE_FIRST '+msg);return null;};
  if(ev==='workflow_run') {
    const r=p.workflow_run;
    if(p.action!=='completed'||!r||
       !new Set([...featureStages.map(x=>x.name),deployment]).has(r.name)||
       r.head_branch!=='main'||(r.head_repository||{}).full_name!==full||
       ['pull_request','pull_request_target'].includes(r.event))
      return log('IGNORE_UNTRUSTED_EVENT');
  } else if(ev==='issues') {
    if(p.action!=='edited'||(p.issue||{}).number!==605)
      return log('IGNORE_OTHER_ISSUE');
  } else if(ev==='push') {
    if(context.ref!=='refs/heads/main'||(p.repository||{}).full_name!==full)
      return log('IGNORE_NONMAIN');
  } else if(ev!=='workflow_dispatch') {
    return log('IGNORE_OTHER_EVENT');
  }
  const issue=(await github.rest.issues.get({owner,repo,issue_number:605})).data;
  // #605 is now a Markdown table, not the old "- [ ] **G-xx**" list.
  // Parse only the authoritative dashboard, never historical entries or
  // completed subtasks embedded inside the main task description.
  const body=issue.body||'';
  const begin='<!-- GALLERY_DASHBOARD_START -->';
  const end='<!-- GALLERY_DASHBOARD_END -->';
  const start=body.indexOf(begin), stop=body.indexOf(end);
  const dashboard=start>=0&&stop>start
    ?body.slice(start+begin.length,stop):body;
  // The active 2026-11-14 table supersedes embedded historical [ ] entries.
  // Backwards compatibility: older 11-ID ledgers still parse as before.
  const modernAt=dashboard.indexOf('## 유한 개발 / 상시 수집');
  const modern=modernAt>=0;
  const modernEnd=modern?dashboard.indexOf('## 자율개발 기준',modernAt):-1;
  const active=modern
    ?dashboard.slice(modernAt,modernEnd>modernAt?modernEnd:undefined)
    :dashboard;
  const states=new Map(),perpetual=new Set();
  for(const line of active.split('\n')) {
    const item=/^- \[([ xX])\] \*\*(G-\d\d)\*\*(?:\s|$)/.exec(line);
    if(item&&!states.has(item[2])&&!modern) {
      states.set(item[2],item[1].toLowerCase()==='x');
      continue;
    }
    if(!line.trim().startsWith('|'))continue;
    const cells=line.trim().split('|').slice(1,-1).map(x=>x.trim());
    if(cells.length<4||!/^G-\d\d$/.test(cells[1]))continue;
    if(modern) {
      if(cells[0]==='무기한 반복') {
        perpetual.add(cells[1]);
        continue; // It must NEVER be counted as a finite completed G-ID.
      }
      if(cells[0]!=='완료형')continue;
    }
    const gate=/\[([ xX])\]/.exec(cells[3]);
    if(gate&&!states.has(cells[1]))
      states.set(cells[1],gate[1].toLowerCase()==='x');
  }
  if(modern) {
    const finite=['G-01','G-02','G-04','G-05','G-06','G-07','G-08','G-09','G-10','G-11'];
    for(const id of finite)if(!states.has(id))
      return log('BLOCK_MISSING_FINITE_LEDGER '+id);
    for(const id of ['G-03','G-12'])if(!perpetual.has(id))
      return log('BLOCK_MISSING_PERPETUAL_COLLECTION '+id);
    core.info('GALLERY_FINITE_DASHBOARD_PARSED_DONE '+
      finite.filter(id=>states.get(id)).length+'/10 PERPETUAL G-03,G-12');
  } else {
    for(let i=1;i<=11;i++) {
      if(!states.has('G-'+String(i).padStart(2,'0')))
        return log('BLOCK_INCOMPLETE_LEDGER G-'+String(i).padStart(2,'0'));
    }
    core.info('GALLERY_DASHBOARD_PARSED_DONE '+[...states].filter(([,done])=>done).length+'/11');
  }
  const remaining=featureStages.filter(x=>!states.get(x.id));
  if(!remaining.length) return log(modern
    ?'FINITE_FEATURES_COMPLETE_PERPETUAL_COLLECTION_ACTIVE'
    :'FEATURES_CHECKED_COLLECTION_STILL_PAUSED');

  const sha=(await github.rest.git.getRef({owner,repo,ref:'heads/main'})).data.object.sha;
  // Never run a browser audit before its actual main Pages deployment.
  const pages=(await github.rest.actions.listWorkflowRuns({
    owner,repo,workflow_id:'static.yml',branch:'main',per_page:100
  })).data.workflow_runs;
  if(!Array.isArray(pages)) return log('MISSING_PAGES_RUNS');
  if(pages.some(r=>r.head_sha===sha&&
    ['queued','pending','in_progress','waiting','requested'].includes(r.status)))
    return log('WAIT_PAGES');
  let published=pages.some(r=>r.head_sha===sha&&r.conclusion==='success');
  if(!published) {
    // Native Pages may skip/cancel intermediary commits while another app
    // pushes. Never wait for an exact repository SHA when the deployed gallery
    // trees are literally unchanged. Never accept only a similar version label.
    for(const candidate of pages.filter(r=>r.conclusion==='success'&&
        r.head_branch==='main'&&r.head_sha!==sha).slice(0,3)) {
      try {
        if(await samePublishedGalleryTrees(github,owner,repo,sha,candidate.head_sha)) {
          published=true;
          core.info('GALLERY_PAGES_TREE_EQUIVALENT '+candidate.head_sha+' '+sha);
          break;
        }
      } catch(error) {
        core.warning('GALLERY_PAGES_EQUIVALENCE_UNAVAILABLE '+error.name);
        break; // fail closed; no invented deployed gallery equivalence
      }
    }
  }
  if(!published) return log('WAIT_SUCCESSFUL_PAGES_OR_SAME_GALLERY_TREES');
  // A verified audit at this same revision is evidence that this STAGE
  // was attempted, not that its entire G-xx issue is complete. Move to the
  // next unfinished independent feature instead of waiting for a checkbox.
  // At most one new workflow is dispatched per GitHub completion event.
  for(const next of remaining) {
    const history=(await github.rest.actions.listWorkflowRuns({
      owner,repo,workflow_id:next.wf,branch:'main',per_page:100
    })).data.workflow_runs;
    if(!Array.isArray(history)) return log('UNVERIFIED_QA_HISTORY '+next.id);
    if(history.some(r=>r.head_branch==='main'&&
      ['queued','pending','in_progress','waiting','requested'].includes(r.status)))
      return log('QA_ALREADY_RUNNING '+next.id);
    if(history.some(r=>r.head_sha===sha&&
      !['pull_request','pull_request_target'].includes(r.event))) {
      core.info('GALLERY_FEATURE_FIRST_ALREADY_TRIED '+next.id);
      continue;
    }
    await github.rest.actions.createWorkflowDispatch({
      owner,repo,workflow_id:next.wf,ref:'main'
    });
    core.notice('GALLERY_FEATURE_FIRST_DISPATCH '+next.id+' '+next.wf+' '+sha.slice(0,12));
    return next.id;
  }
  return log('ALL_INDEPENDENT_FEATURE_QA_ATTEMPTED_AT_SHA');
};
