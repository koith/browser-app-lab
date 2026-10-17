'use strict';
const REVISION='4leaf-revival-pwa-v68';
// 32 genuinely archived 145×97 original TIS platform images. First offline
// Genesis match must draw the same extracted raised platforms, not replace
// uncached native source art with a CSS placeholder on first room entry.
const NATIVE_TIS_FILES='0000 0001 0006 0007 0008 0009 0010 0011 0012 0013 0014 0015 0016 0017 0018 0019 0020 0021 0022 0023 0024 0025 0026 0027 0028 0029 0030 0031 0035 0041 0043 0046'.split(' ');
const CORE=['./','./index.html','./pwa-runtime.js','./manifest.webmanifest','./icon.svg','./game.js','./style.css','./original.css','./lobby.css','./game-authentic.css','./network.css','./network.js','./original-shell-accurate.css','./mainframe-native-toolbar.css','./original/MainFrame/toolbarbtn.png','./original/MainFrame/pannel.png','./shop-native.js','./cardshop-native-controls.css','./cardshop-original-2003.css','./cardshop-native-controls.js','./original/CardShop/cardshopbutton.png','./dice-native-stage.js','./dice-native-stage.css','./dice-native-map-buttons.css','./dice-native-map-buttons.js','./dice-native-room-buttons.js','./dice-native-room-buttons.css','./original/Room/roombutton.png','./original/Map/mapbutton.png','./original/Map/maplist.png','./town-native-room-hotspots.css','./native-chattown-scale.css','./knighttown-native.js','./knighttown-native.css','./original/KnightTown/knightback.png','./original/KnightTown/sea01.png','./original/KnightTown/sea02.png','./original/KnightTown/sea03.png','./original/KnightTown/snow01.png','./original/KnightTown/plain01.png','./original/KnightTown/plain02.png','./original-chat-input.css','./chatroom-native-exit.css','./chatroom-native-exit.js','./chatroom-native-talkbox.css','./chatroom-native-talkbox.js','./dice-native-player-portraits.css','./original/IMG/avatarback.png','./dice-native-chessmen-hud.css','./dice-original-selector.css','./dice-native-menu-chrome.css','./dice-native-dialog-event.css','./original/IMG/dialog.png','./original/IMG/eventmsgbox.png','./original/IMG/menu.png','./original/MainFrame/toolbarbtn.png','./board-camera.js','./dice-dmp-camera-controls.css','./dice-source-dmp-terrain-explorer.js','./dice-source-dmp-terrain-explorer.css','./dice-native-tis-clean.css','./dice-native-battle-podium.css','./dice-native-battle-dice.css','./dice-2004-full-frame.css','./dice-source-roll.css','./dice-source-roll.js','./dice-source-native-ui.css','./dice-source-native-chat-scroll.js','./original/IMG/okcancelbut.png','./original/IMG/scrollbutton.png','./original/IMG/stats.png','./dice-fall.js','./dice-fall.css','./genesis-chessman-actors.js','./genesis-chessman-actors.css','./original/IMG/selector.png','./original/CardData/chm_12.png','./original/CardData/chm_33.png','./original/CardData/chm_8.png','./chatroom-native-panels.css','./chatroom-native-ringbtn.css','./chatroom-native-scrollbar.css','./chatroom-native-scrollbar.js','./original/ChatRoom/scrollbar.png','./original/ChatRoom/ringbtn.png','./chatroom-native-panels.js','./chatroom-native-owner-dialog.js','./chatroom-native-owner-dialog.css','./registry-native-avatar-dialog.js','./registry-native-avatar-dialog.css','./original/Registry/avatardialog1.png','./original/Registry/avatardialog2.png','./original/Registry/avatardialog3.png','./chatroom-native-expressions.js','./chatroom-native-expressions.css','./original/ChatRoom/expdialogbtn.png','./original/ChatRoom/ownerdialog.png','./original/ChatRoom/talkbox.png','./original/ChatRoom/exitbtn.png','./original-world-notice.css','./original/WorldMap/notice.png','./original/ChatRoom/chatbaredit.png','./original/Map/mapback.png','./original/Room/roomback.png','./original/MainFrame/title.png','./original/MainFrame/borderbtn.png','./original/CardShop/cardshopback.png','./central-client.js','./world-map.js','./world-social.css','./world-map-source-moon.css','./social-chat.js','./lobby-ui.js','./original/maps.js','./original/tiles.js','./original/chessmen.js','./original/Gif/d1lobby.png','./original/Gif/d1waitroom.png','./original/WorldMap/worldmapback.png','./original/CardShop/cardshopback.png','./original/IMG/bgtile.png','./dice-native-client-frame.css','./dice-native-minimap-navigation.css','./dice-native-client-frame.js','./original/IMG/chatwnd.png','./original/IMG/abilitybar.png','./original/IMG/topbar.png','./original/IMG/minimap.png','./original/WorldMap/mainstreet.png','./original/WorldMap/knights.png','./original/WorldMap/northchatrgn.png','./original/WorldMap/southchatrgn.png','./original/WorldMap/dice.png','./original/WorldMap/m4leaf.png','./original/ChatTown/northback.png','./original/ChatTown/southback.png','./original/ChatTown/plainbtn.png','./original/ChatTown/seabtn.png','./original/ChatTown/snowbtn.png','./original/ChatRoom/room0.png','./original/ChatRoom/room1.png','./original/ChatRoom/room2.png','./original/ChatRoom/room3.png','./original/ChatRoom/room4.png','./original/ChatRoom/room5.png','./original/ChatRoom/room3t.png','./original/ChatRoom/room4t.png','./original/ChatRoom/room5t.png','./original/Registry/sava00.png','./original/Registry/sava82.png','./original/Registry/sava06.png','./original/Registry/sava01.png','./original/Registry/sava85.png','./original/Registry/sava02.png','./original/Registry/sava84.png','./original/Registry/sava04.png','./original/Registry/sava03.png','./original/Registry/sava83.png','./original/Registry/sava05.png','./original/Registry/sava86.png','./mainframe-native-snapshot.js','./mainframe-native-snapshot.css','./original/MainFrame/snaplogo.png','./original/MainFrame/snapnumber.png','./original/MainFrame/wallpaper.png','./dice-native-tis-depth.css','./dice-native-tis-orientation.css','./dice-ai-autoplay.css','./dice-native-pawn-dmp-depth.css','./dice-native-tis-alpha.js'].concat(
 NATIVE_TIS_FILES.map(name=>'./original/Tiles/'+name+'.png')
).concat(['./original/OBS/animation-manifest.js','./original/OBS/animation-extra.js','./dice-original-obs.css',
 './dice-source-tile-pitch.css','./dice-d4-source-fallback.css',
 './dice-source-chessman-battle.css',
 ...['1042-00','1042-01','1042-02','1042-03','1042-10','1042-18','1042-25','1042-30',
 '1045-00','1045-01','1045-02','1045-10','1045-18'].map(id=>'./original/OBS/'+id+'.png')]);
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
 // During a restoration rollout, old cache-first JS/CSS silently keeps
 // broken dice handlers and tile CSS alive after a successful Pages deploy.
 // Fetch executable/style updates first while online; retain offline cache.
 const url=new URL(request.url);
 // Match actual executable/style paths. The previous /\\\\./ expression
 // accidentally matched a backslash, NEVER .js/.css; it silently kept
 // the old cache-first dice handlers after a successful deployment.
 const scopePath=new URL('./',self.registration.scope).pathname;
 if(url.pathname.startsWith(scopePath)&&
   (url.pathname.endsWith('.js')||url.pathname.endsWith('.css'))){
  event.respondWith(fetch(request,{cache:'no-cache'}).then(async response=>{
   if(response.ok&&response.type==='basic'){
    const cache=await caches.open(REVISION);
    await cache.put(request,response.clone());
   }
   return response;
  }).catch(async()=>await caches.match(request)||Response.error()));
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