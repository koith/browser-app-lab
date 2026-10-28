'use strict';
const assert=require('node:assert/strict'),fs=require('fs'),path=require('path');
const P=require('./publishers.js'),L=require('./gallery-labels.js');
const registry=JSON.parse(fs.readFileSync(path.join(__dirname,'publishers.json')));
const albums=[{id:'a',title:'SWEETBOX — Work',images:[{}]},{id:'b',publisher:'BCUT',images:[]},{id:'c',publisher:'GamerSky',collection_kind:'public_editorial_photos',images:[{}]},{id:'d',title:'Unknown',images:[]}];
const groups=P.groups(albums,registry,L.describe,a=>a.images||[]);
assert.deepEqual(groups.map(g=>g.id),['public','bcut','unknown','sweetbox']);
assert.equal(groups.find(g=>g.id==='bcut').viewable,0);
assert.equal(groups.find(g=>g.id==='public').albums[0].id,'c');
assert.deepEqual(['Vol.10','vol.2','Vol.1'].sort(P.compareNames),['Vol.1','vol.2','Vol.10']);
assert.equal(P.key({publisher:'CTEE'},registry,L.describe),'ctee');
assert.equal(P.key({publisher:'DJAWA',collection_kind:'official_public_samples'},registry,L.describe),'djawa');
assert.equal(P.logo({logo:{path:'https://example.org/fake.svg',verified_official:true}}),null);
assert.equal(P.logo({logo:{path:'publisher-logos/fake.svg',verified_official:false}}),null);
for(const p of registry.publishers){
 if(!p.logo)continue;
 const asset=P.logo(p);assert.ok(asset,'Verified local logo path for '+p.id);
 const bytes=fs.readFileSync(path.join(__dirname,asset)),hash=require('crypto').createHash('sha256').update(bytes).digest('hex');
 assert.equal(hash,p.logo.sha256);assert.equal(bytes.length,p.logo.bytes);
 assert.match(p.logo.source_url,/^https:\/\//);assert.match(p.logo.origin_page,/^https:\/\//);
}
console.log('PUBLISHER_ATTRIBUTION_PUBLIC_COLLECTION_SEPARATION_AND_LOGO_BYTES_PASS',groups.length);
