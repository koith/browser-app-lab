/* 4LEAF live world camera — follows actual game entities across original .mve coordinates.
   Deliberately NOT a screenshot compositor: every board tile is a live DOM game entity.
   The historical 3D client showed a zoomed slice of the map, not every card at once. */
(function(){
 'use strict';
 const SIZE={width:1450,height:1120};
 const state={game:null,path:null,scale:1,panX:0,panY:0,cameraX:null,cameraY:null,manual:false,lastTurn:null};
 const $=id=>document.getElementById(id);
 const clamp=(n,low,high)=>Math.min(high,Math.max(low,n));
 const camera={
   sync(game,path){
     if(!game||!Array.isArray(path)||!path.length||!$('board-area'))return;
     state.game=game;state.path=path;
     const current=game.players?.[game.active];
     if(current){
       const p=path[clamp(Number(current.position)||0,0,path.length-1)];
       if(p){
         state.cameraX=SIZE.width*(p.x/100);
         state.cameraY=SIZE.height*(p.y/100);
         if(state.lastTurn!==game.active){state.manual=false;state.panX=0;state.panY=0}
         state.lastTurn=game.active;
       }
     }
     camera.render();
   },
   viewport(zoom,panX=0,panY=0){
     state.scale=clamp(Number(zoom)||1,0.65,2.4);
     state.panX=Number(panX)||0;state.panY=Number(panY)||0;
     state.manual=state.panX!==0||state.panY!==0;
     camera.render();
   },
   zoom(delta){
     state.scale=clamp(Math.round((state.scale+delta)*100)/100,0.65,2.4);
     camera.render();
   },
   reset(){
     state.scale=1;state.panX=0;state.panY=0;state.manual=false;
     camera.render();
   },
   render(){
     const area=$('board-area'),world=$('board-world');
     if(!area||!world||state.cameraX===null)return;
     const width=area.clientWidth,height=area.clientHeight;
     if(width<20||height<20)return;
     const scale=state.scale;
     const worldW=SIZE.width*scale,worldH=SIZE.height*scale;
     let x=width*.49-state.cameraX*scale+state.panX,
         y=height*.52-state.cameraY*scale+state.panY;
     x=worldW>=width?clamp(x,width-worldW,0):(width-worldW)/2;
     y=worldH>=height?clamp(y,height-worldH,0):(height-worldH)/2;
     world.style.transform='translate3d('+x.toFixed(2)+'px,'+y.toFixed(2)+'px,0) scale('+scale+')';
     world.style.setProperty('--leaf-camera-scale',scale);
     if($('board-zoom-reset'))$('board-zoom-reset').title='원본 게임 카메라 · '+Math.round(scale*100)+'% · 현재 체스맨 중심';
     const tileLayer=$('board-nodes');
     if(tileLayer){
       for(const tile of tileLayer.children){
         const point=state.path[Number(tile.dataset.tile)];
         if(!point)continue;
         const sx=point.x/100*SIZE.width*scale+x,sy=point.y/100*SIZE.height*scale+y;
         tile.style.visibility=(sx < -120 || sy < -100 || sx>width+120 || sy>height+110)?'hidden':'visible';
       }
     }
   },
   getState(){return {...state,size:{...SIZE}}}
 };
 window.__LEAF_CAMERA__=camera;
 if('ResizeObserver' in window){
   const observe=()=>{const e=$('board-area');if(e)new ResizeObserver(()=>camera.render()).observe(e)};
   if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',observe);
   else observe();
 }
})();
