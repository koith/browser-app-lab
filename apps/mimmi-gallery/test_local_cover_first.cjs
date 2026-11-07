'use strict';
/* Covers need not await Render when the same SHA-verified bytes exist on Pages.
 * This test executes the real gallery card() implementation, not a re-creation.
 */
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const vm=require('node:vm');
const root=__dirname;
const page=fs.readFileSync(path.join(root,'index.html'),'utf8');
const start=page.indexOf('function card(a,hasImages){');
const end=page.indexOf('\nfunction photoHTML(',start);
assert.ok(start>=0&&end>start,'Real gallery card function must be present');
const source=page.slice(start,end);
const sha='a'.repeat(64);
const ownerPhoto={number:1,storageNumber:1,sha256:sha,bytes:123456,width:900,height:1350,
  url:'owner:safe-work:1',ownerAlbum:'safe-work',preview:'previews/safe-work/1.webp'};
const pagesPhoto={...ownerPhoto,url:'stored-albums/safe-work/1.jpg'};
delete pagesPhoto.ownerAlbum;
delete pagesPhoto.storageNumber;
delete pagesPhoto.preview;
const album={id:'safe-work',title:'Safe Work',images:[ownerPhoto],expected:10};
function render(owner,local,additionalSaved=[]){
 const env={
  location:{hostname:'koith.github.io'},
  stored:owner?[{...album,images:[owner,...additionalSaved]}]:[{...album,images:[local]}],
  localStored:local?[{...album,images:[local]}]:[],
  localPreviewIndex:new Map(),
  catalog:[album],albumCovers:{},
  validImages:a=>a.images||[],
  getName:a=>a.title||a.id,
  MimmiLabels:{describe:()=>({publisher:'Publisher',edition:'Edition',kind:'portrait',detail:'Photo'}),coverTitle:a=>a.title},
  rotationAttributes:()=>'',canonicalId:id=>id,
  esc:s=>String(s??'').replace(/&/g,'&amp;').replace(/"/g,'&quot;')
 };
 vm.createContext(env);
 vm.runInContext(source+';rebuildLocalPreviewIndex();globalThis.cardForTest=card;',env,{filename:'mimmi-real-card.js'});
 return env.cardForTest(album,true);
}
const exact=render(ownerPhoto,pagesPhoto);
assert.ok(exact.includes('src="stored-albums/safe-work/1.jpg"'), 'Must paint SHA-identical stored Pages bytes first');
assert.ok(exact.includes('data-owner="owner:safe-work:1"'), 'Private original route must be retained');
assert.ok(exact.includes('data-owner-variant="local"'), 'Fallback must know this is a Pages copy');
assert.ok(page.includes("img.dataset.ownerVariant==='local'")&&page.includes("MimmiPrivate.asset(p,'cover')"),
  'Broken Pages image must fall back to matching verified owner cover');
const differentSHA=render(ownerPhoto,{...pagesPhoto,sha256:'b'.repeat(64)});
assert.ok(!differentSHA.includes('src="stored-albums/safe-work/1.jpg"'),
  'Different photo or unproven variant must never replace the saved owner cover');
assert.ok(differentSHA.includes('data-owner="owner:safe-work:1"'));
const wrongBytes=render(ownerPhoto,{...pagesPhoto,bytes:123457});
assert.ok(!wrongBytes.includes('src="stored-albums/safe-work/1.jpg"'),
  'A same-SHA record with inconsistent byte evidence is not an eligible cover');
const wrongDimensions=render(ownerPhoto,{...pagesPhoto,width:901});
assert.ok(!wrongDimensions.includes('src="stored-albums/safe-work/1.jpg"'),
  'Mismatched decoded image evidence cannot be used as the fallback');
const staticOnly=render(null,pagesPhoto);
assert.ok(staticOnly.includes('src="stored-albums/safe-work/1.jpg"')&&!staticOnly.includes('data-owner='),
  'Already-public-only photos remain directly viewable');
const alternative={...pagesPhoto,number:2,sha256:'b'.repeat(64),url:'stored-albums/safe-work/2.jpg'};
const sameWorkAlternative=render(ownerPhoto,alternative,[alternative]);
assert.ok(sameWorkAlternative.includes('src="stored-albums/safe-work/2.jpg"'),
  'A verified photo in the same composed work must paint when the preferred private cover has no exact saved copy');
assert.ok(!sameWorkAlternative.includes('data-owner='),
  'An actual committed alternative does not need the unavailable Render cover request');
assert.equal(ownerPhoto.ownerAlbum,'safe-work','Choosing a cover must not mutate the private original');

const owner=JSON.parse(fs.readFileSync(path.join(root,'owner-index.json'),'utf8'));
const local=JSON.parse(fs.readFileSync(path.join(root,'stored-albums.json'),'utf8'));
const byId=new Map(local.albums.map(a=>[a.id,a]));
let eligible=0,both=0;
for(const a of owner.albums){
 const saved=byId.get(a.id);
 if(!saved?.images?.length)continue;
 both++;
 const first=saved.images[0];
 if(a.images.some(p=>p.sha256===first.sha256&&p.bytes===first.bytes&&
                         p.width===first.width&&p.height===first.height))eligible++;
}
assert.ok(eligible>0,'There must be real SHA-identical local covers to justify this optimization');
console.log('MIMMI_EXACT_SHA_LOCAL_FIRST_CARD_AND_PRIVATE_FALLBACK_PASS',
  JSON.stringify({both_stores_works:both,eligible_local_first_works:eligible}));
