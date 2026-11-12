'use strict';
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const {describe,coverTitle}=require('./gallery-labels.js');
const publishers=require('./publishers.js');
const registry=JSON.parse(fs.readFileSync(path.join(__dirname,'publishers.json')));
for(const [id,title,expected] of [
 ['djawa-pop-kitty-party','Pop Kitty Party','DJAWA'],
 ['djawa-rudy2-codename-wolfgirl-9b4e68','Rudy² – Codename : Wolfgirl','DJAWA'],
 ['v2ph-actor-a93xn3oa','[DJAWA] Mimmi - Cream Cow Milk - Page 2','DJAWA'],
 ['v2ph-actor-z4m9x9xa','DJAWA Photo - Mimmi Christmas Special','DJAWA'],
 ['v2ph-actor-z4xoo5nz','[CreamSoda] Mimmi Vol.5 Mash Mimmi 2','CreamSoda'],
 ['xiutu-public-1190145','[CreamSoda] Mimmi Belt choker','CreamSoda'],
 ['mimmi-indie-sana-sopmod2-2019','밈미 — SANA 개인 촬영','독립 화보'],
 ['artgravia-700-mimmi','ArtGravia Vol.700','ArtGravia']
]){
 const a={id,title};
 assert.equal(describe(a).publisher,expected,'publisher attribution must not be Yui labels: '+id);
 assert.notEqual(publishers.key(a,registry,describe),'unknown','known work should not be labelled unknown: '+id);
}
for(const a of [
 {id:'v2ph-actor-unknown',title:'Mimmi cosplay mirror',source:'https://www.v2ph.com/album/some.html'},
 {id:'pixibb-mirror-unknown',title:'Unknown publisher',source:'https://cosplay.pixibb.com/album'}
]) assert.equal(describe(a).publisher,'미확인','mirror host must not masquerade as original publisher');
assert.equal(describe({title:'Mimmi',publisher_original_verified:true}).edition,'원본');
assert.equal(describe({title:'Mimmi',ai_enhanced:true}).edition,'AI 보정판');
assert.equal(coverTitle({id:'v2ph-actor-a93xn3oa',title:'[DJAWA] Mimmi - Cream Cow Milk - Page 2'}),
 'Mimmi - Cream Cow Milk - Page 2');
assert.equal(coverTitle({id:'xiutu-public-1190145',title:'[CreamSoda] Mimmi Belt choker'}),
 'Mimmi Belt choker');
const owner=JSON.parse(fs.readFileSync(path.join(__dirname,'owner-index.json')));
const local=JSON.parse(fs.readFileSync(path.join(__dirname,'stored-albums.json')));
let mapped=0,unmapped=[];
const byId=new Map();
for(const a of [...local.albums,...owner.albums])byId.set(a.id,a);
for(const a of byId.values()){
 if(publishers.key(a,registry,describe)==='unknown')unmapped.push(a.id);
 else mapped++;
}
assert.deepEqual(unmapped,[],'All 80 saved Mimmi works must have a publisher attribution or independent category');
console.log('G10_MIMMI_REAL_80_WORK_PUBLISHER_LABELS_PASS',JSON.stringify({mapped}));
