// Regression for essentialGalleryJSON in both gallery entrypoints.
// Run: node .github/scripts/test-gallery-essential-json-retry.cjs
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
async function run(path) {
 const html = fs.readFileSync(path, 'utf8');
 const start = html.indexOf('async function essentialGalleryJSON(');
 const end = html.indexOf('\n}\n', start);
 assert(start >= 0 && end > start, 'function present');
 const source = html.slice(start, end + 2);
 for (const [statuses, expectedCalls, succeeds] of [
  [[503, 200], 2, true],
  [[502, 503, 200], 3, true],
  [[504, 200], 2, true],
  [[401, 200], 1, false],
  [[403, 200], 1, false],
  [[404, 200], 1, false],
  [[200], 1, false],
 ]) {
  let calls = 0;
  const context = {
   AbortController, Error, TypeError, Promise,
   // Only fire retry backoffs; never fire the 10-second abort watchdog.
   // A no-op timer leaves the awaited retry promise permanently unresolved.
   setTimeout: (fn, ms) => { if (ms < 10000) queueMicrotask(fn); return 1; },
   clearTimeout: () => {},
   fetch: async () => {
    const status = statuses[calls++] || 200;
    return { ok: status === 200, status, json: async () => status === 200 && statuses.length === 1 ? {invalid:true} : {albums:[]} };
   },
  };
  vm.createContext(context);
  vm.runInContext(source + '\nthis.load = essentialGalleryJSON;', context);
  let success = false;
  try { await context.load('stored-albums.json', 'archive', d => Array.isArray(d.albums)); success = true; }
  catch (_) {}
  assert.equal(success, succeeds, path + ' ' + statuses);
  assert.equal(calls, expectedCalls, path + ' request count ' + statuses);
 }

 // The owner index is also an essential JSON manifest. For 401/403/404
 // and broken schema, fail promptly; only transient same-origin 5xx retry.
 const first=html.indexOf('async function fetchOwnerIndexWithRetry(');
 const last=html.indexOf('\\n}\\n',first);
 assert(first>=0&&last>first,'owner retry function present');
 const ownerSource=html.slice(first,last+2);
 for(const [statuses,expectedCalls,succeeds] of [
  [[503,200],2,true],[[502,504,200],3,true],
  [[401,200],1,false],[[403,200],1,false],[[404,200],1,false],
  [[200],1,false],
 ]) {
  let calls=0;
  const context={
   AbortController,Error,TypeError,Promise,console:{warn:()=>{}},
   setTimeout:(fn,ms)=>{if(ms<12000)queueMicrotask(fn);return 1;},
   clearTimeout:()=>{},
   fetch:async()=>{
    const status=statuses[calls++]||200;
    const model=path.includes('mimmi')?'mimmi':'yui';
    return {ok:status===200,status,json:async()=>statuses.length===1
      ?{schema_version:999,model,albums:[]}
      :{schema_version:1,model,albums:[]}};
   },
  };
  vm.createContext(context);
  vm.runInContext(ownerSource+'\\nthis.loadOwner=fetchOwnerIndexWithRetry;',context);
  let succeeded=false;
  try{await context.loadOwner(path.includes('mimmi')?'mimmi':'yui');succeeded=true}
  catch(_){}
  assert.equal(succeeded,succeeds,path+' owner '+statuses);
  assert.equal(calls,expectedCalls,path+' owner calls '+statuses);
 }
}
(async () => {
 await run('apps/mimmi-gallery/index.html');
 await run('apps/yui-gallery/index.html');
 console.log('GALLERY_ESSENTIAL_JSON_RETRY_ACCESS_DENIAL_SCHEMA_TRANSIENT_PASS');
})().catch(e => { console.error(e); process.exitCode=1; });
