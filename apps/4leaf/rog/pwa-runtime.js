'use strict';
/* Real PWA registration for the published 4LEAF web app.
 * The previous Chromium offline tests explicitly registered sw.js, but the
 * actual index.html never did. Offline installs and future dice/TIS repairs
 * therefore could not be relied on in ordinary browser visits.
 * Registration never blocks or reloads live games. */
(function(){
 const state={supported:'serviceWorker' in navigator&&window.isSecureContext,
  registered:false,controlled:false,error:null};
 const status=()=>({...state,controlled:Boolean(navigator.serviceWorker?.controller)});
 window.__LEAF_PWA__={getState:status};
 if(!state.supported)return;
 navigator.serviceWorker.addEventListener('controllerchange',()=>{
  state.controlled=Boolean(navigator.serviceWorker.controller);
 });
 const install=async()=>{
  try{
   const registration=await navigator.serviceWorker.register('./sw.js',{
    scope:'./',updateViaCache:'none'
   });
   state.registered=true;
   state.controlled=Boolean(navigator.serviceWorker.controller);
   // Chromium/iOS may keep a previous worker active on a returning tab.
   // Checking for an update must not force a reload during a match.
   try{await registration.update()}
   catch(error){state.error=String(error?.message||error).slice(0,140)}
  }catch(error){
   state.error=String(error?.message||error).slice(0,140);
   console.warn('4LEAF offline worker unavailable; online play remains active',error);
  }
 };
 if(document.readyState==='loading')
  document.addEventListener('DOMContentLoaded',install,{once:true});
 else void install();
})();
