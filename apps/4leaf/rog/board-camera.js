/* 4LEAF live world camera — follows actual game entities across original .mve coordinates.
   Deliberately NOT a screenshot compositor: every board tile is a live DOM game entity.
   The historical 3D client showed a zoomed slice of the map, not every card at once. */
(function(){
 'use strict';
 // DMP coordinates remain integer logical map cells, 70x47 source pitch.
 // Each native TIS card is 145x97; its DMP source grid is only 70x47.
 // 2004 board.jpg/battle.jpg historical photographs show individually
 // legible upper faces of the raised hexes, not the interleaved sprite row
 // produced by the earlier 111x75 WEB pitch (34px horizontal, 22px vertical
 // overlap between 145x97 native TIS images). A 130x86 projected pitch
 // retains a physically plausible shallow 15x11 overlap / raised lip,
 // while leaving the original 70x47 DMP LOGICAL coordinates untouched.
 // The historic MVE projection/camera is unrecovered: these rendering
 // distances are provisional photo-calibrated values, never archive facts.
 const SOURCE_GRID={width:1450,height:1120,pitchX:70,pitchY:47};
 const SIZE={width:2650,height:2050};
 const PROJECTED_PITCH={x:70*SIZE.width/SOURCE_GRID.width,
  y:47*SIZE.height/SOURCE_GRID.height};
 const state={game:null,path:null,scale:1,panX:0,panY:0,cameraX:null,cameraY:null,manual:false,lastTurn:null,visible:null};
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
     return camera.getState();
   },
   // The recovered IMG/minimap.png is a TRUE working navigator, not a
   // painted sample. Its coordinates are normalized over the original DMP
   // route extents, and never alter actual pawn positions or player turns.
   focusRatio(rx,ry){
     if(state.cameraX===null||!Number.isFinite(rx)||!Number.isFinite(ry))
       return camera.getState();
     const x=clamp(rx,0,1)*SIZE.width,y=clamp(ry,0,1)*SIZE.height;
     state.panX=(state.cameraX-x)*state.scale;
     state.panY=(state.cameraY-y)*state.scale;
     state.manual=true;
     camera.render();
     return camera.getState();
   },
   panBy(dx,dy){
     if(!Number.isFinite(dx)||!Number.isFinite(dy))return camera.getState();
     state.panX+=dx;state.panY+=dy;state.manual=true;
     camera.render();
     return camera.getState();
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
     const anchorX=width*.49-state.cameraX*scale,
           anchorY=height*.52-state.cameraY*scale;
     // Clamp to the source-grid-preserving, screen-projected DMP route;
     // not the old zoom-only limit of 1/8 of the viewport. Every source
     // cell must be accessible even at 65%-100% zoom.
     const x=worldW>=width?clamp(anchorX+state.panX,width-worldW,0):(width-worldW)/2,
           y=worldH>=height?clamp(anchorY+state.panY,height-worldH,0):(height-worldH)/2;
     state.panX=worldW>=width?x-anchorX:0;
     state.panY=worldH>=height?y-anchorY:0;
     // Exactly the same clamped screen rectangle the source camera paints;
     // no independent guessed minimap box or fictitious world coordinates.
     state.visible={
       x:clamp(-x/(SIZE.width*scale),0,1),
       y:clamp(-y/(SIZE.height*scale),0,1),
       width:clamp(width/(SIZE.width*scale),0,1),
       height:clamp(height/(SIZE.height*scale),0,1)
     };
     world.style.transform='translate3d('+x.toFixed(2)+'px,'+y.toFixed(2)+'px,0) scale('+scale+')';
     world.style.setProperty('--leaf-camera-scale',scale);
     if($('board-zoom-reset'))$('board-zoom-reset').title='원본 게임 카메라 · '+Math.round(scale*100)+'% · 현재 체스맨 중심';
     const tileLayer=$('board-nodes');
     if(tileLayer){
       for(const tile of tileLayer.children){
         const point=state.path[Number(tile.dataset.tile)];
         if(!point)continue;
         const sx=point.x/100*SIZE.width*scale+x,sy=point.y/100*SIZE.height*scale+y;
         // The native sprite is a 145x97 platform. Keep partially visible
         // pieces at high zoom; fixed 120px culling margins wrongly
         // disappeared 2.4x platforms while they were still on-screen.
         const radiusX=73*scale+2,radiusY=49*scale+2;
         tile.style.visibility=(sx < -radiusX || sy < -radiusY ||
           sx>width+radiusX || sy>height+radiusY)?'hidden':'visible';
       }
     }
     window.__LEAF_MINIMAP_NAV__?.onCameraRender?.();
   },
   getState(){return {...state,size:{...SIZE},sourceGrid:{...SOURCE_GRID},projectedPitch:{...PROJECTED_PITCH},visible:state.visible?{...state.visible}:null}}
 };
 window.__LEAF_CAMERA__=camera;
 if('ResizeObserver' in window){
   const observe=()=>{const e=$('board-area');if(e)new ResizeObserver(()=>camera.render()).observe(e)};
   if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',observe);
   else observe();
 }
})();
