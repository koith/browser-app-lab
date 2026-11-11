'use strict';
// G-05: execute the real gallery canonicalId/validImages functions, not a reimplementation.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const html = fs.readFileSync(require('node:path').join(__dirname, 'index.html'), 'utf8');
function functionSource(name) {
  const start = html.indexOf('function ' + name + '(');
  assert.ok(start >= 0, 'missing function ' + name);
  const brace = html.indexOf('{', start);
  let depth = 0, quote = '', escape = false;
  for (let i = brace; i < html.length; i++) {
    const c = html[i];
    if (quote) {
      if (escape) escape = false;
      else if (c === '\\') escape = true;
      else if (c === quote) quote = '';
    } else if (c === '"' || c === "'" || c === '`') quote = c;
    else if (c === '{') depth++;
    else if (c === '}' && --depth === 0) return html.slice(start, i + 1);
  }
  throw Error('unclosed function ' + name);
}
const context = vm.createContext({});
vm.runInContext('let stored=[],albumAliases={};' + functionSource('validImages') + functionSource('canonicalId') +
  ';globalThis.setData=(a,b)=>{stored=a;albumAliases=b};globalThis.resolve=canonicalId;', context);
const sha = 'a'.repeat(64);
const owner = (id, n=1) => ({ownerAlbum:id,number:n,url:'owner:'+id+':'+n,sha256:sha,bytes:62786});
const album = (id, images) => ({id,images});
const aliases = {v04:'teddy-bear97',h06:'teddy-bear97'};
const target = album('teddy-bear97',[owner('teddy-bear97')]);
const exact = album('v04',[owner('v04')]);
context.setData([exact,target],aliases);
assert.equal(context.resolve('v04'),'v04','verified independent album must not be replaced by alias');
assert.equal(context.resolve('h06'),'teddy-bear97','alias without independent album must still resolve');
context.setData([album('v04',[{...owner('v04'),sha256:'invalid'}]),target],aliases);
assert.equal(context.resolve('v04'),'teddy-bear97','invalid SHA must not authorize independent owner album');
context.setData([album('v04',[{...owner('v04'),url:'owner:teddy-bear97:1'}]),target],aliases);
assert.equal(context.resolve('v04'),'teddy-bear97','wrong owner URL must not authorize independent album');
context.setData([album('v04',[{...owner('v04'),ownerAlbum:'teddy-bear97'}]),target],aliases);
assert.equal(context.resolve('v04'),'teddy-bear97','wrong ownerAlbum must not authorize independent album');
context.setData([exact],aliases);
assert.equal(context.resolve('v04'),'v04','exact owner album must work without alias target');
console.log('G05_CANONICAL_OWNER_ALIAS_REGRESSION_PASS 6/6');
