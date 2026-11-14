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
 rare.title='원본 2004 화면의 RARE 탭 · 역사 자료상 출시 RARE 0종 · EXE 분류표 미복구';
 rare.setAttribute('aria-label','RARE 원본 탭 · 발매 기록 0종 (원본 EXE 분류표 미복구)');
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
 // The recovered 2002 UI does not contain a time-machine control.
 // Keep this WEB-only provenance switch visually separate from source art.
 const marketLabel=document.createElement('label');
 marketLabel.className='shop-market-date-label';marketLabel.textContent='2003 시세 ';
 const marketSelect=document.createElement('select');
 marketSelect.id='shop-market-date';
 marketSelect.setAttribute('aria-label','2003년 매직카덴 기록 시세 날짜');
 for(const [value,label] of [['2003-01-05','1월 5일'],['2003-01-15','1월 15일']]){
  const option=document.createElement('option');option.value=value;option.textContent=label;
  marketSelect.append(option);
 }
 marketSelect.value=window.__LEAF_HISTORIC_MARKET__?.getState().date||'2003-01-05';
 marketLabel.append(marketSelect);toolbar.append(marketLabel);
 marketSelect.addEventListener('change',()=>{
  window.__LEAF_HISTORIC_MARKET__?.setDate(marketSelect.value);
  renderProvenance();
 });
 const provenance=document.createElement('div');
 provenance.id='shop-era-provenance';
 provenance.setAttribute('role','status');
 stage.append(provenance);
 const renderProvenance=()=>{
  const market=window.__LEAF_HISTORIC_MARKET__?.getState();
  const note=market?.date==='2003-01-15'
   ?' · 1/15 원본 변경가 6종만 확정, 그 외 1/5 기록 유지(1/15 미검증)'
   :' · 1/5 당시 신문 가격 97종(원본 EXE 가격표 아님)';
  provenance.textContent=(era==='2004'
   ?'2004 캡처 기반 4×2 / RARE 명단 미확보(역사상 발매 0종) · 구성 비교용'
   :'2002 PAK 원본 3×3 / 원본 배경·버튼')+note;
 };
 window.addEventListener('leaf-shop-market-change',()=>{
  const source=window.__LEAF_HISTORIC_MARKET__?.getState();
  if(source&&marketSelect.value!==source.date)marketSelect.value=source.date;
  renderProvenance();
 });
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
  renderProvenance();
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
