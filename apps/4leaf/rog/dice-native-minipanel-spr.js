/* ORIGINAL 2002 Dice/IMG.pak minipanel.spr: four genuine 75x20 native
 * minimap/chessman-info tab states. Keep the canvas-based DMP minimap alive,
 * not a wallpaper. The historical CONTENT layout of the information panel
 * was not recovered; all values below come from the real selected chessman.
 */
(function(){
 'use strict';
 function install(){
  const root=document.getElementById('board-mini'),canvas=document.getElementById('mini-map-canvas');
  const party=document.getElementById('dice-native-party');
  if(!root||!canvas||!party||root.dataset.nativePanelInstalled)return;
  root.dataset.nativePanelInstalled='true';
  root.dataset.nativePanelSource='Dice/IMG.pak:minipanel.spr';
  root.dataset.nativePanelFrames='4';
  root.dataset.historicalInfoLayout='unverified-web-real-card-data';
  root.dataset.activePanel='map';
  const tabs=document.createElement('div');
  tabs.className='leaf-native-minipanel-tabs';
  const views=[['map','미니맵'],['info','체스맨정보']];
  const buttons=views.map(([key,title])=>{
   const b=document.createElement('button');
   b.type='button';b.className='leaf-native-minipanel-tab';
   b.dataset.panel=key;
   b.title=title;b.setAttribute('aria-label',title);
   b.setAttribute('aria-pressed',String(key==='map'));
   b.dataset.originalSourceMember='Dice/IMG.pak:minipanel.spr';
   b.addEventListener('click',()=>{
    root.dataset.activePanel=key;
    buttons.forEach(n=>n.setAttribute('aria-pressed',String(n===b)));
    canvas.setAttribute('aria-hidden',String(key==='info'));
    content.setAttribute('aria-hidden',String(key!=='info'));
    if(key==='info')refresh();
   });
   tabs.append(b);return b;
  });
  const content=document.createElement('div');
  content.className='leaf-native-minipanel-content';
  content.id='leaf-native-chessman-info';
  content.setAttribute('role','region');
  content.setAttribute('aria-label','현재 선택한 출전 체스맨');
  content.setAttribute('aria-hidden','true');
  const picture=document.createElement('img');
  picture.className='leaf-native-minipanel-face';picture.alt='';picture.draggable=false;
  const detail=document.createElement('div');
  detail.className='leaf-native-minipanel-detail';
  const name=document.createElement('strong'),stats=document.createElement('span');
  detail.append(name,stats);content.append(picture,detail);
  root.append(tabs,content);
  function refresh(){
   const slot=party.querySelector('.dice-chessman-slot.selected .dice-chessman-face')?.closest('.dice-chessman-slot')||
    party.querySelector('.dice-chessman-slot.occupied');
   const img=slot?.querySelector('.dice-chessman-face');
   const source=img?.getAttribute('src')||'';
   if(source&&picture.getAttribute('src')!==source)picture.src=source;
   picture.hidden=!source;
   name.textContent=slot?.querySelector('b')?.textContent||'출전 체스맨 없음';
   stats.textContent=slot?.title?.replace(/^.+? \/ /,'')||'실제 출전 카드를 선택해 주세요';
   content.dataset.sourceCardId=slot?.dataset.cardId||'';
   content.dataset.sourceCardArtwork=source;
   content.dataset.dataSource='real-selected-party-card-not-fabricated-player';
  }
  new MutationObserver(()=>{
   if(root.dataset.activePanel==='info')refresh();
  }).observe(party,{subtree:true,childList:true,attributes:true,
   attributeFilter:['class','data-selected-index']});
  refresh();
  window.__LEAF_NATIVE_MINIPANEL__={
   select:key=>buttons.find(n=>n.dataset.panel===key)?.click(),
   getState:()=>({view:root.dataset.activePanel,source:root.dataset.nativePanelSource,
    frames:4,layoutVerified:false,card:content.dataset.sourceCardId,
    image:picture.getAttribute('src'),tabs:buttons.map(x=>({panel:x.dataset.panel,
     pressed:x.getAttribute('aria-pressed')}))})
  };
 }
 if(document.readyState==='loading')
  document.addEventListener('DOMContentLoaded',install,{once:true});
 else install();
})();