'use strict';

// #605: feature-first handoff. Image discovery, crawling and TeraBox writes
// are paused until the user explicitly reauthorizes them. No timer or chats.
module.exports = async function featureHandoff({github, context, core}) {
  const owner=context.repo.owner, repo=context.repo.repo;
  const full=owner+'/'+repo, ev=context.eventName, p=context.payload;
  const featureStages=[
    {id:'G-09',wf:'gallery-first-image-metrics.yml',
      name:'Gallery — First Image Latency and Full SHA Coverage'},
    {id:'G-10',wf:'gallery-quality-branding-entry-qa.yml',
      name:'Gallery Quality Branding and Fast Entry Regression QA'},
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
  const states=new Map();
  for(const line of (issue.body||'').split('\n')) {
    const m=/^- \[([ xX])\] \*\*(G-\d\d)\*\*(?:\s|$)/.exec(line);
    if(m&&!states.has(m[2])) states.set(m[2],m[1].toLowerCase()==='x');
  }
  for(let i=1;i<=11;i++) {
    if(!states.has('G-'+String(i).padStart(2,'0')))
      return log('BLOCK_INCOMPLETE_LEDGER');
  }
  const next=featureStages.find(x=>!states.get(x.id));
  if(!next) return log('FEATURES_CHECKED_COLLECTION_STILL_PAUSED');

  const sha=(await github.rest.git.getRef({owner,repo,ref:'heads/main'})).data.object.sha;
  // Never run a browser audit before its actual main Pages deployment.
  const pages=(await github.rest.actions.listWorkflowRuns({
    owner,repo,workflow_id:'static.yml',branch:'main',per_page:100
  })).data.workflow_runs;
  if(!Array.isArray(pages)) return log('MISSING_PAGES_RUNS');
  if(pages.some(r=>r.head_sha===sha&&
    ['queued','pending','in_progress','waiting','requested'].includes(r.status)))
    return log('WAIT_PAGES');
  const published=pages.some(r=>r.head_sha===sha&&r.conclusion==='success');
  if(!published) return log('WAIT_SUCCESSFUL_PAGES');
  const history=(await github.rest.actions.listWorkflowRuns({
    owner,repo,workflow_id:next.wf,branch:'main',per_page:100
  })).data.workflow_runs;
  if(!Array.isArray(history)) return log('UNVERIFIED_QA_HISTORY');
  if(history.some(r=>r.head_branch==='main'&&
    ['queued','pending','in_progress','waiting','requested'].includes(r.status)))
    return log('QA_ALREADY_RUNNING '+next.id);
  if(history.some(r=>r.head_sha===sha&&
    !['pull_request','pull_request_target'].includes(r.event)))
    return log('QA_ALREADY_ATTEMPTED '+next.id);
  // Dispatch one allowlisted QA workflow. A passing QA is not proof that
  // the feature is complete; only a separately verified #605 checkbox
  // transition promotes the next feature. No image collection is dispatched.
  await github.rest.actions.createWorkflowDispatch({
    owner,repo,workflow_id:next.wf,ref:'main'
  });
  core.notice('GALLERY_FEATURE_FIRST_DISPATCH '+next.id+' '+next.wf+' '+sha.slice(0,12));
  return next.id;
};
