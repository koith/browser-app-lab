'use strict';

// Event-driven handoff for #605. No cron, background ChatGPT thread or
// automatic completion claims. Only existing, allowlisted GitHub workflows.
module.exports = async function handoff({github, context, core}) {
  const owner=context.repo.owner, repo=context.repo.repo;
  const full=owner+'/'+repo, ev=context.eventName, p=context.payload;
  const collect='gallery-direct-individual-archive.yml';
  const deploy='static.yml';
  const browser='gallery-deployed-pages-photo-qa.yml';
  const exact='gallery-newly-stored-photo-qa.yml';
  const stages=[collect,'gallery-reverse-full-corpus-ab.yml',
    'gallery-exhaustive-engines-audit.yml','gallery-visual-quality-audit.yml',
    'gallery-first-image-metrics.yml','gallery-quality-branding-entry-qa.yml',browser];
  const allowedNames=new Set([
    'Gallery Direct Individual Photo Collection and Verified Storage',
    'Yui Mimmi ALL Owner Albums Reverse Image and Named Work Source Comparison',
    'Yui Mimmi Exhaustive Registered Gallery Collector Comparison',
    'Gallery Real Image Pixel Quality Audit',
    'Gallery — First Image Latency and Full SHA Coverage',
    'Gallery Quality Branding and Fast Entry Regression QA',
    'Deploy static content to Pages',
    'Yui Mimmi Deployed GitHub Pages Real Photo Browser QA',
    'Gallery Newly Stored Exact Original Mobile QA']);
  const hold=(reason)=>{core.info('GALLERY_HANDOFF_HOLD '+reason);return null;};
  if(ev==='workflow_run') {
    const r=p.workflow_run;
    if(p.action!=='completed' || !r || !allowedNames.has(r.name) ||
       r.head_branch!=='main' || (r.head_repository||{}).full_name!==full ||
       ['pull_request','pull_request_target'].includes(r.event))
       return hold('untrusted workflow source');
  } else if(ev==='issues') {
    if(p.action!=='edited' || (p.issue||{}).number!==605) return hold('other issue');
  } else if(ev==='push') {
    if(context.ref!=='refs/heads/main' || (p.repository||{}).full_name!==full)
      return hold('non-main push');
  } else if(ev!=='workflow_dispatch') return hold('unrelated event');

  const issue=(await github.rest.issues.get({owner,repo,issue_number:605})).data;
  function priority(body) {
    const found=new Map();
    for(const line of (body||'').split('\n')) {
      const m=/^- \[([ xX])\] \*\*(G-\d\d)\*\*(?:\s|$)/.exec(line);
      if(m && !found.has(m[2])) found.set(m[2],m[1].toLowerCase()==='x');
    }
    for(let i=1;i<=11;i++) {
      const t='G-'+String(i).padStart(2,'0');
      if(!found.has(t)) return 'INVALID';
    }
    for(let i=1;i<=11;i++) {
      const t='G-'+String(i).padStart(2,'0');
      if(!found.get(t)) return t;
    }
    return null;
  }
  const task=priority(issue.body);
  if(!task || task==='INVALID') return hold('ledger '+(task||'all checked'));
  const sha=(await github.rest.git.getRef({owner,repo,ref:'heads/main'})).data.object.sha;
  const cache=new Map();
  async function runs(wf) {
    if(![...stages,exact,deploy].includes(wf)) throw Error('unapproved workflow query');
    if(!cache.has(wf)) {
      const data=(await github.rest.actions.listWorkflowRuns({
        owner,repo,workflow_id:wf,branch:'main',per_page:100})).data;
      if(!Array.isArray(data.workflow_runs)) throw Error('unverified Action history');
      cache.set(wf,data.workflow_runs);
    }
    return cache.get(wf);
  }
  const active=r=>['queued','in_progress','pending','waiting','requested'].includes(r.status);
  const atSha=r=>r.head_sha===sha &&
    !['pull_request','pull_request_target'].includes(r.event);
  async function dispatch(wf) {
    if(![...stages,exact].includes(wf)) throw Error('non-allowlisted dispatch');
    await github.rest.actions.createWorkflowDispatch({
      owner,repo,workflow_id:wf,ref:'main'});
    core.notice('GALLERY_HANDOFF_DISPATCH '+task+' '+wf+' '+sha.slice(0,12));
    return wf;
  }

  const allCollectors=await runs(collect);
  const previousCollector=allCollectors.find(r=>r.status==='completed' &&
    r.head_branch==='main' && !['pull_request','pull_request_target'].includes(r.event));
  let newlyIndexed=false;
  if(ev==='workflow_run' && previousCollector &&
     /^[a-f0-9]{40}$/.test(previousCollector.head_sha) &&
     previousCollector.head_sha!==sha) {
    try {
      const result=(await github.rest.repos.compareCommitsWithBasehead({
        owner,repo,basehead:previousCollector.head_sha+'...'+sha})).data;
      if(!Array.isArray(result.files)) return hold('commit diff evidence unavailable');
      newlyIndexed=result.files.some(f=>[
        'apps/mimmi-gallery/owner-index.json',
        'apps/yui-gallery/owner-index.json'].includes(f.filename));
    } catch(e) {return hold('cannot verify collector index diff');}
  }

  // Collector can publish the catalog and invoke Pages immediately. Its
  // previously simultaneous QA dispatches are not sufficient: both browser
  // and exact-new-original verification must finish AFTER Pages deploy.
  if(newlyIndexed) {
    const deployments=(await runs(deploy)).filter(r=>atSha(r)&&r.conclusion==='success');
    if(!deployments.length) return hold('waiting for Pages deployment');
    const last=deployments[0];
    const after=r=>atSha(r)&&r.conclusion==='success' &&
      Date.parse(r.created_at)>=Date.parse(last.updated_at);
    const webPassed=(await runs(browser)).some(after);
    const exactRuns=(await runs(exact)).filter(after);
    if(!exactRuns.length) {
      if(!(await runs(exact)).some(r=>active(r)&&atSha(r))) await dispatch(exact);
      return hold('post-deployment original SHA QA pending');
    }
    let originalsPassed=false;
    for(const r of exactRuns) {
      const jobs=(await github.rest.actions.listJobsForWorkflowRun({
        owner,repo,run_id:r.id,per_page:100})).data.jobs;
      if(Array.isArray(jobs) && jobs.some(j=>
        j.name.startsWith('actual-deployed-originals') &&
        j.conclusion==='success')) {originalsPassed=true;break;}
    }
    if(!webPassed || !originalsPassed)
      return hold('waiting for post-Pages Chromium/WebKit and original SHA');
  }

  // These other audits may run while G-03 still lacks new official photos;
  // an audit success never means that the photo task is complete.
  const followup={
    'G-05':[collect], 'G-06':[stages[1]], 'G-07':[stages[2]],
    'G-08':[stages[3]], 'G-09':[stages[4]], 'G-10':[stages[5]],
    'G-11':[stages[6]]
  };
  const choices=task==='G-03'?stages:(followup[task]||[]);
  const before=ev==='issues' && (p.changes||{}).body
    ?priority(p.changes.body.from):null;
  for(const wf of choices) {
    const hist=await runs(wf);
    if(hist.some(r=>active(r)&&r.head_branch==='main'))
      return hold('already active '+wf);
    const tried=hist.some(atSha);
    // G-03 and G-05 share the collector. A verified #605 transition is
    // the one safe case where reusing the workflow at the same SHA is allowed.
    const promoted=ev==='issues' && task==='G-05' &&
      before==='G-03' && wf===collect;
    if(tried && !promoted) continue;
    if(newlyIndexed && wf===collect) continue;
    return dispatch(wf);
  }
  return hold('all approved stages attempted at this revision; no false completion');
};
