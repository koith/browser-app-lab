'use strict';
const REVISION='4leaf-revival-pwa-v37';
const CORE=['./','./index.html','./game.js','./style.css','./original.css','./lobby.css','./game-authentic.css','./network.css','./network.js','./original-shell-accurate.css','./shop-native.js','./cardshop-native-controls.css','./cardshop-original-2003.css','./cardshop-native-controls.js','./original/CardShop/cardshopbutton.png','./dice-native-stage.js','./dice-native-stage.css','./dice-native-map-buttons.css','./dice-native-map-buttons.js','./dice-native-room-buttons.js','./dice-native-room-buttons.css','./original/Room/roombutton.png','./original/Map/mapbutton.png','./original/Map/maplist.png','./town-native-room-hotspots.css','./native-chattown-scale.css','./original-chat-input.css','./chatroom-native-exit.css','./chatroom-native-exit.js','./chatroom-native-talkbox.css','./chatroom-native-talkbox.js','./dice-native-player-portraits.css','./original/IMG/avatarback.png','./dice-native-chessmen-hud.css','./dice-original-selector.css','./dice-native-menu-chrome.css','./original/IMG/menu.png','./original/MainFrame/toolbarbtn.png','./dice-native-tis-clean.css','./dice-native-battle-podium.css','./original/IMG/selector.png','./original/CardData/chm_12.png','./original/CardData/chm_33.png','./original/CardData/chm_8.png','./chatroom-native-panels.css','./chatroom-native-ringbtn.css','./chatroom-native-scrollbar.css','./chatroom-native-scrollbar.js','./original/ChatRoom/scrollbar.png','./original/ChatRoom/ringbtn.png','./chatroom-native-panels.js','./original/ChatRoom/talkbox.png','./original/ChatRoom/exitbtn.png','./original-world-notice.css','./original/WorldMap/notice.png','./original/ChatRoom/chatbaredit.png','./original/Map/mapback.png','./original/Room/roomback.png','./original/MainFrame/title.png','./original/MainFrame/borderbtn.png','./original/CardShop/cardshopback.png','./central-client.js','./world-map.js','./world-map-source-moon.css','./social-chat.js','./lobby-ui.js','./original/maps.js','./original/tiles.js','./original/chessmen.js','./original/Gif/d1lobby.png','./original/Gif/d1waitroom.png','./original/WorldMap/worldmapback.png','./original/CardShop/cardshopback.png','./original/IMG/bgtile.png','./dice-native-client-frame.css','./dice-native-client-frame.js','./original/IMG/chatwnd.png','./original/IMG/abilitybar.png','./original/IMG/topbar.png','./original/IMG/minimap.png','./original/MainFrame/wallpaper.png'];
self.addEventListener('install',event=>{
 event.waitUntil(caches.open(REVISION).then(async cache=>{
   const requests=CORE.map(path=>new Request(new URL(path,self.registration.scope),{cache:'reload'}));
   await Promise.allSettled(requests.map(request=>cache.add(request)));
   await self.skipWaiting();
 }));
});
self.addEventListener('activate',event=>{
 event.waitUntil((async()=>{
   const keys=await caches.keys();await Promise.all(keys.filter(k=>k.startsWith('4leaf-revival-pwa-')&&k!==REVISION).map(k=>caches.delete(k)));
   await self.clients.claim();
 })());
});
self.addEventListener('fetch',event=>{
 const request=event.request;
 if(request.method!=='GET'||new URL(request.url).origin!==self.location.origin)return;
 if(request.mode==='navigate'){
   event.respondWith(fetch(request).then(async response=>{
     if(response.ok)(await caches.open(REVISION)).put(request,response.clone());
     return response;
   }).catch(async()=>await caches.match(request)||await caches.match(new URL('./',self.registration.scope))||Response.error()));
   return;
 }
 event.respondWith(caches.match(request).then(cached=>{
   const refresh=fetch(request).then(async response=>{
     if(response.ok&&response.type==='basic'&&new URL(request.url).pathname.includes('/apps/4leaf/rog/')){
       const cache=await caches.open(REVISION);cache.put(request,response.clone());
     }
     return response;
   }).catch(()=>cached||Response.error());
   return cached||refresh;
 }));
});