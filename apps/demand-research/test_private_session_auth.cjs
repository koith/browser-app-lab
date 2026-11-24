// No network, real credentials, account identifiers, or archived records.
const { test } = require('node:test');
const assert = require('node:assert/strict');
const vm = require('node:vm');
const fs = require('node:fs');
const path = require('node:path');
const html = fs.readFileSync(path.join(__dirname, 'index.html'), 'utf8');
const scripts = [...html.matchAll(/<script(?:\s[^>]*)?>([\s\S]*?)<\/script>/gi)];
const candidates = scripts.map(x => x[1]).filter(x =>
  x.includes('INTERSECTION_AUTH_READY') && x.includes('/api/activate'));
assert.equal(candidates.length, 1, 'one private session bootstrap expected');
const script = candidates[0];
const trusted = 'https://intersection-originals-free.onrender.com';
async function scenario(url, { historyFail=false, fetchFail=false, ok=true }={}) {
  const location = new URL(url);
  const calls=[], events=[], replaced=[];
  const window={dispatchEvent:e=>events.push(e.type)};
  vm.runInNewContext(script, {
    window, location, URLSearchParams, Event,
    history:{replaceState(_,__,value) {
      if(historyFail) throw Error('blocked');
      replaced.push(value);
    }},
    fetch:async(path,opts)=>{
      calls.push({path,opts,historyClean:replaced.length>0});
      if(fetchFail) throw Error('offline');
      return {ok};
    }
  });
  return {ready:await window.INTERSECTION_AUTH_READY,calls,events,replaced};
}
test('exact HTTPS origin scrubs before POST',async()=>{
  const r=await scenario(trusted+'/p?q=1#access=synthetic');
  assert.equal(r.ready,true);
  assert.deepEqual(r.replaced,['/p?q=1']);
  assert.equal(r.calls.length,1);
  assert.equal(r.calls[0].historyClean,true);
  assert.equal(JSON.parse(r.calls[0].opts.body).token,'synthetic');
  assert.equal(r.calls[0].path,'/api/activate');
  assert.equal(r.calls[0].opts.credentials,'same-origin');
  assert.deepEqual(r.events,['intersection:private-session-ready']);
});
for(const url of [
  'https://koith.github.io/p#access=synthetic',
  'http://intersection-originals-free.onrender.com/p#access=synthetic',
  'https://intersection-originals-free.onrender.com:444/p#access=synthetic',
  'https://intersection-originals-free.onrender.com.example.org/p#access=synthetic'
]) test('untrusted origin '+url.split('#')[0],async()=>{
  const r=await scenario(url);
  assert.equal(r.ready,false);
  assert.deepEqual(r.replaced,['/p']);
  assert.equal(r.calls.length,0);
});
test('empty and duplicate tokens scrubbed without POST',async()=>{
  for(const hash of ['#access=','#access=a&access=b']){
    const r=await scenario(trusted+'/p'+hash);
    assert.equal(r.ready,false);
    assert.deepEqual(r.replaced,['/p']);
    assert.equal(r.calls.length,0);
  }
});
test('other fragment values preserved',async()=>{
  const r=await scenario(trusted+'/p#tab=archive&access=x&view=grid');
  assert.deepEqual(r.replaced,['/p#tab=archive&view=grid']);
});
test('no token leaves URL unchanged',async()=>{
  const r=await scenario(trusted+'/p#section');
  assert.equal(r.ready,false);
  assert.equal(r.replaced.length,0);
  assert.equal(r.calls.length,0);
});
test('failed history replacement blocks POST',async()=>{
  const r=await scenario(trusted+'/p#access=x',{historyFail:true});
  assert.equal(r.ready,false);
  assert.equal(r.calls.length,0);
});
test('network and HTTP failures report false',async()=>{
  for(const opts of [{fetchFail:true},{ok:false}]){
    const r=await scenario(trusted+'/p#access=x',opts);
    assert.equal(r.ready,false);
    assert.equal(r.events.length,0);
  }
});
