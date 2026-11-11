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
// SavedGalleryPhotoUnion may replace an owner route with a byte-identical
// committed Pages file. The album still owns that exact SHA and must win.
const local=(id)=>({number:1,url:'stored-albums/'+id+'/0001.jpg',sha256:sha,bytes:62786,width:512,height:776});
context.setData([album('v04',[local('v04')]),target],aliases);
assert.equal(context.resolve('v04'),'v04','committed exact Pages album must not be redirected to an alias');
context.setData([album('v04',[{...local('v04'),url:'stored-albums/teddy-bear97/0011.jpg',originalAlbumId:'teddy-bear97',shaPinnedLocalCopy:true}]),target],aliases);
assert.equal(context.resolve('v04'),'v04','SHA-pinned owner original replicated under a different physical album must stay in its exact logical album');
context.setData([album('v04',[{...local('v04'),url:'stored-albums/other/0001.jpg'}]),target],aliases);
assert.equal(context.resolve('v04'),'teddy-bear97','wrong unpinned physical URL must not preserve a distinct album');
console.log('G05_CANONICAL_OWNER_ALIAS_REGRESSION_PASS 9/9');
