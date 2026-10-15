'use strict';
// CardShop/cardshopback.png is a native 794×404 screen, not a stretchable
// 16:9 wallpaper. Wrap existing functional controls in one native coordinate
// space, scale uniformly, and retain the original untouched bitmap behind them.
(function(){
 const SIZE={width:794,height:404};
 const scene=document.querySelector('#shop .shop-scene');
 if(!scene)return;
 const stage=document.createElement('div');
 stage.className='shop-native-stage';
 stage.id='shop-native-stage';
 stage.setAttribute('data-source','CardShop/cardshopback.png');
 while(scene.firstChild)stage.append(scene.firstChild);
 scene.append(stage);
 function fit(){
  const width=scene.clientWidth,height=scene.clientHeight;
  if(!width||!height)return;
  const factor=Math.min(width/SIZE.width,height/SIZE.height);
  const x=(width-SIZE.width*factor)/2,y=(height-SIZE.height*factor)/2;
  stage.style.transform='translate3d('+x.toFixed(2)+'px,'+y.toFixed(2)+'px,0) scale('+factor+')';
  stage.dataset.scale=factor.toFixed(6);
 }
 if('ResizeObserver' in window)new ResizeObserver(fit).observe(scene);
 window.addEventListener('resize',fit,{passive:true});
 fit();
 window.__LEAF_SHOP_STAGE__={fit,getState:()=>({
  width:SIZE.width,height:SIZE.height,scale:Number(stage.dataset.scale)||0,
  viewportWidth:scene.clientWidth,viewportHeight:scene.clientHeight
 })};
})();