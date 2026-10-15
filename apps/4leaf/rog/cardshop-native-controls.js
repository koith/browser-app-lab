'use strict';
// Original CardShop/ cardshopback.png includes the right-side 장비 caption.
// Keep the recovered bitmap unobstructed until the real inventory is requested.
// This is a functioning toggle around the existing game-owned card list.
(function(){
 const init=()=>{
  const stage=document.getElementById('shop-native-stage');
  const panel=document.querySelector('#shop .shop-equipped');
  const list=document.getElementById('shop-owned-list');
  if(!stage||!panel||!list)return;
  const toggle=document.createElement('button');
  toggle.id='shop-owned-toggle';
  toggle.type='button';toggle.className='shop-owned-toggle';
  toggle.setAttribute('aria-label','보유 체스맨 카드 목록 열기');
  toggle.setAttribute('aria-controls','shop-owned-list');
  toggle.setAttribute('aria-expanded','false');
  toggle.title='장비 · 보유 카드 열기';
  const setOpen=open=>{
   stage.classList.toggle('owned-open',open);
   toggle.setAttribute('aria-expanded',String(open));
   toggle.setAttribute('aria-label',open?'보유 체스맨 카드 목록 닫기':'보유 체스맨 카드 목록 열기');
   toggle.title=open?'장비 · 보유 카드 닫기':'장비 · 보유 카드 열기';
  };
  toggle.addEventListener('click',()=>setOpen(!stage.classList.contains('owned-open')));
  stage.addEventListener('keydown',event=>{
   if(event.key!=='Escape'||!stage.classList.contains('owned-open'))return;
   setOpen(false);toggle.focus();event.stopPropagation();
  });
  // Preserve CardShop page transitions: only close the drawer when leaving
  // the actual shop, never reset user's selected card/filter or purchase data.
  document.addEventListener('leaf-route-change',event=>{
   if(event.detail?.route!=='shop')setOpen(false);
  });
  stage.append(toggle);
  window.__LEAF_SHOP_NATIVE__={
   getState:()=>({
    ownerPanelOpen:stage.classList.contains('owned-open'),
    toggle:toggle.getAttribute('aria-expanded'),
    stage:stage.dataset.source,
    visibleCards:[...document.querySelectorAll('#shop-grid .shop-card:not(.shop-empty)')].length,
    selectedCard:document.querySelector('#shop-grid .shop-card.selected')?.dataset.cardId||null
   }),
   openInventory:()=>setOpen(true),
   closeInventory:()=>setOpen(false)
  };
 };
 if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',init);
 else init();
})();
