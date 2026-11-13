'use strict';
/* Compare TWO authentic historical versions without pretending that the
 * recovered 2002 CardShop 3x3 atlas is the later 2004 4x2 screenshot.
 * 2004 layout is an independently drawn DOM reconstruction; source CHR
 * names/card bodies and transactions remain live. 2004 RARE membership is
 * explicitly UNVERIFIED and never inferred from a high numeric stat. */
(function(){
 const stage=document.getElementById('shop-native-stage');
 if(!stage)return;
 const tabs=stage.querySelector('.shop-stock .tabline');
 if(!tabs)return;
 const rare=document.createElement('button');
 rare.type='button';rare.className='group-tab';
 rare.dataset.group='rare';rare.textContent='RARE';
 rare.title='원본 2004 화면에 있는 RARE 분류. 현재 원본 카드 분류표 미복구';
 rare.setAttribute('aria-label','RARE (원본 카드 분류 데이터 미복구)');
 tabs.append(rare);
 const toolbar=document.createElement('div');
 toolbar.id='shop-era-toggle';toolbar.className='shop-era-toggle';
 toolbar.setAttribute('role','group');toolbar.setAttribute('aria-label','원본 매직카덴 연도별 화면');
 for(const era of ['2002','2004']){
  const b=document.createElement('button');b.type='button';
  b.dataset.era=era;b.textContent=era;
  b.setAttribute('aria-label',era+'년 매직카덴 화면 선택');
  toolbar.append(b);
 }
 stage.append(toolbar);
 const provenance=document.createElement('div');
 provenance.id='shop-era-provenance';
 provenance.setAttribute('role','status');
 stage.append(provenance);
 let era='2002';
 try{era=localStorage.getItem('4leaf-original-shop-era')==='2004'?'2004':'2002'}catch{}
 const apply=(selected,persist)=>{
  if(!['2002','2004'].includes(selected))return false;
  era=selected;
  stage.dataset.era=era;
  for(const b of toolbar.querySelectorAll('button')){
   b.setAttribute('aria-pressed',String(b.dataset.era===era));
  }
  rare.disabled=era!=='2004';
  if(era==='2002'&&rare.classList.contains('selected')){
   tabs.querySelector('[data-group="all"]')?.click();
  }
  provenance.textContent=era==='2004'
   ?'2004 캡처 기반 4×2 화면 / RARE 명단 미확보 · 구성 비교용'
   :'2002 CardShop.pak 원본 3×3 / 원본 버튼·배경';
  if(persist){try{localStorage.setItem('4leaf-original-shop-era',era)}catch{}}
  window.__ROG_TEST__?.drawShop?.();
  window.dispatchEvent(new CustomEvent('leaf-shop-era-change',{detail:{era,sourceRarity:'unverified'}}));
  return true;
 };
 for(const b of toolbar.querySelectorAll('button'))b.addEventListener('click',()=>apply(b.dataset.era,true));
 window.__LEAF_SHOP_ERA__={setEra:s=>apply(s,true),getState:()=>({
  era,pageSize:era==='2004'?8:9,
  originalAsset:era==='2004'?'archived-2004-shop_ref.png-reference/independent-DOM':'2002-CardShop/cardshopback.png',
  rareMembershipVerified:false,rareTabVisible:era==='2004'
 })};
 apply(era,false);
})();
