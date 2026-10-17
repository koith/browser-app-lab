'use strict';
const REVISION='4leaf-revival-pwa-v69';
// 32 genuinely archived 145×97 original TIS platform images. First offline
// Genesis match must draw the same extracted raised platforms, not replace
// uncached native source art with a CSS placeholder on first room entry.
const NATIVE_OBS_BULK_FILES='1043-00 1043-01 1043-02 1043-03 1043-10 1043-30 1044-00 1044-01 1044-02 1044-10 1050-00 1050-01 1050-02 1050-18 1050-30 1052-00 1052-01 1052-02 1052-10 1052-18 1052-30 1053-00 1053-01 1053-02 1054-00 1054-01 1054-02 1054-03 1054-10 1054-18 1054-25 1054-30 1058-00 1058-01 1058-02 1058-03 1058-10 1059-00 1059-01 1059-02 1059-10 1059-18 1060-00 1060-01 1060-02 1060-03 1060-10 1060-18 1060-25 1062-00 1062-01 1062-02 1062-03 1062-10 1062-18 1062-25 1062-30 1063-00 1063-01 1063-02 1063-03 1063-18 1063-30 1066-00 1066-01 1066-02 1066-10 1066-18 1067-00 1067-01 1067-02 1067-03 1067-18 1067-25 1067-30 1068-00 1068-01 1068-02 1068-03 1068-10 1068-18 1068-25 1068-30 1069-00 1069-01 1069-02 1069-03 1069-10 1069-18 1069-25 1069-30 1071-00 1071-01 1071-02 1071-03 1071-18 1071-25 1072-00 1072-01 1072-02 1072-10 1073-00 1073-01 1073-02 1073-10 1073-18 1073-30 1074-00 1074-01 1074-03 1074-18 1074-25 1074-30 1075-00 1075-01 1075-02 1076-00 1076-01 1076-02 1078-00 1078-01 1078-02 1079-00 1079-01 1079-02 1079-03 1079-10 1080-00 1080-01 1080-02 1081-00 1081-01 1081-02 1081-03 1081-10 1081-18 1081-25 1081-30 1082-00 1082-01 1082-02 1082-03 1082-10 1082-30 1084-00 1084-01 1084-02 1084-03 1084-10 1084-18 1084-25 1084-30 1086-00 1086-01 1086-02 1086-03 1086-10 1088-00 1088-01 1088-02 1088-03 1088-10 1088-18 1088-25 1088-30 1090-00 1090-02 1090-03 1090-25 1090-30 1094-00 1094-01 1094-02 1094-03 1125-00 1125-01 1125-02 1125-03 1125-10 1127-00 1127-01 1127-02 1127-03 1127-10 1127-18 1127-25 1130-00 1130-01 1130-02 1130-03 1130-10 1130-18 1130-25 1131-00 1131-01 1133-00 1133-01 1133-02 1133-18 1136-00 1136-01 1136-02 1136-03 1141-00 1141-01 1141-03 1142-00 1142-03 1142-10 1142-18 1145-00 1145-02 1147-00 1147-01 1147-03 1167-00 1167-01 1167-02 1167-03 1167-10 1167-18 1170-00 1170-02 1171-00 1171-01 1171-02 1171-03 1171-10 1171-25'.split(' ');
const NATIVE_TIS_FILES='0000 0001 0006 0007 0008 0009 0010 0011 0012 0013 0014 0015 0016 0017 0018 0019 0020 0021 0022 0023 0024 0025 0026 0027 0028 0029 0030 0031 0035 0041 0043 0046'.split(' ');
const CORE=['./','./index.html','./pwa-runtime.js','./manifest.webmanifest','./icon.svg','./game.js','./style.css','./original.css','./lobby.css','./game-authentic.css','./network.css','./network.js','./original-shell-accurate.css','./mainframe-native-toolbar.css','./original/MainFrame/toolbarbtn.png','./original/MainFrame/pannel.png','./shop-native.js','./cardshop-native-controls.css','./cardshop-original-2003.css','./cardshop-native-controls.js','./original/CardShop/cardshopbutton.png','./dice-native-stage.js','./dice-native-stage.css','./dice-native-map-buttons.css','./dice-native-map-buttons.js','./dice-native-room-buttons.js','./dice-native-room-buttons.css','./original/Room/roombutton.png','./original/Map/mapbutton.png','./original/Map/maplist.png','./town-native-room-hotspots.css','./native-chattown-scale.css','./knighttown-native.js','./knighttown-native.css','./original/KnightTown/knightback.png','./original/KnightTown/sea01.png','./original/KnightTown/sea02.png','./original/KnightTown/sea03.png','./original/KnightTown/snow01.png','./original/KnightTown/plain01.png','./original/KnightTown/plain02.png','./original-chat-input.css','./chatroom-native-exit.css','./chatroom-native-exit.js','./chatroom-native-talkbox.css','./chatroom-native-talkbox.js','./dice-native-player-portraits.css','./original/IMG/avatarback.png','./dice-native-chessmen-hud.css','./dice-original-selector.css','./dice-native-menu-chrome.css','./dice-native-dialog-event.css','./original/IMG/dialog.png','./original/IMG/eventmsgbox.png','./original/IMG/menu.png','./original/MainFrame/toolbarbtn.png','./board-camera.js','./dice-dmp-camera-controls.css','./dice-source-dmp-terrain-explorer.js','./dice-source-dmp-terrain-explorer.css','./dice-native-tis-clean.css','./dice-native-battle-podium.css','./dice-native-battle-dice.css','./dice-2004-full-frame.css','./dice-source-roll.css','./dice-source-roll.js','./dice-source-native-ui.css','./dice-source-native-chat-scroll.js','./original/IMG/okcancelbut.png','./original/IMG/scrollbutton.png','./original/IMG/stats.png','./dice-fall.js','./dice-fall.css','./genesis-chessman-actors.js','./genesis-chessman-actors.css','./original/IMG/selector.png','./original/CardData/chm_12.png','./original/CardData/chm_33.png','./original/CardData/chm_8.png','./chatroom-native-panels.css','./chatroom-native-ringbtn.css','./chatroom-native-scrollbar.css','./chatroom-native-scrollbar.js','./original/ChatRoom/scrollbar.png','./original/ChatRoom/ringbtn.png','./chatroom-native-panels.js','./chatroom-native-owner-dialog.js','./chatroom-native-owner-dialog.css','./registry-native-avatar-dialog.js','./registry-native-avatar-dialog.css','./original/Registry/avatardialog1.png','./original/Registry/avatardialog2.png','./original/Registry/avatardialog3.png','./chatroom-native-expressions.js','./chatroom-native-expressions.css','./original/ChatRoom/expdialogbtn.png','./original/ChatRoom/ownerdialog.png','./original/ChatRoom/talkbox.png','./original/ChatRoom/exitbtn.png','./original-world-notice.css','./original/WorldMap/notice.png','./original/ChatRoom/chatbaredit.png','./original/Map/mapback.png','./original/Room/roomback.png','./original/MainFrame/title.png','./original/MainFrame/borderbtn.png','./original/CardShop/cardshopback.png','./central-client.js','./world-map.js','./world-social.css','./world-map-source-moon.css','./social-chat.js','./lobby-ui.js','./original/maps.js','./original/tiles.js','./original/chessmen.js','./original/Gif/d1lobby.png','./original/Gif/d1waitroom.png','./original/WorldMap/worldmapback.png','./original/CardShop/cardshopback.png','./original/IMG/bgtile.png','./dice-native-client-frame.css','./dice-native-minimap-navigation.css','./dice-native-client-frame.js','./original/IMG/chatwnd.png','./original/IMG/abilitybar.png','./original/IMG/topbar.png','./original/IMG/minimap.png','./original/WorldMap/mainstreet.png','./original/WorldMap/knights.png','./original/WorldMap/northchatrgn.png','./original/WorldMap/southchatrgn.png','./original/WorldMap/dice.png','./original/WorldMap/m4leaf.png','./original/ChatTown/northback.png','./original/ChatTown/southback.png','./original/ChatTown/plainbtn.png','./original/ChatTown/seabtn.png','./original/ChatTown/snowbtn.png','./original/ChatRoom/room0.png','./original/ChatRoom/room1.png','./original/ChatRoom/room2.png','./original/ChatRoom/room3.png','./original/ChatRoom/room4.png','./original/ChatRoom/room5.png','./original/ChatRoom/room3t.png','./original/ChatRoom/room4t.png','./original/ChatRoom/room5t.png','./original/Registry/sava00.png','./original/Registry/sava82.png','./original/Registry/sava06.png','./original/Registry/sava01.png','./original/Registry/sava85.png','./original/Registry/sava02.png','./original/Registry/sava84.png','./original/Registry/sava04.png','./original/Registry/sava03.png','./original/Registry/sava83.png','./original/Registry/sava05.png','./original/Registry/sava86.png','./mainframe-native-snapshot.js','./mainframe-native-snapshot.css','./original/MainFrame/snaplogo.png','./original/MainFrame/snapnumber.png','./original/MainFrame/wallpaper.png','./dice-native-tis-depth.css','./dice-native-tis-orientation.css','./dice-ai-autoplay.css','./dice-native-pawn-dmp-depth.css','./dice-native-tis-alpha.js'].concat(
 NATIVE_TIS_FILES.map(name=>'./original/Tiles/'+name+'.png')
).concat(['./original/OBS/animation-manifest.js','./original/OBS/animation-extra.js','./dice-original-obs.css',
 './dice-source-tile-pitch.css','./dice-d4-source-fallback.css',
 './dice-source-chessman-battle.css',
 ...['1042-00','1042-01','1042-02','1042-03','1042-10','1042-18','1042-25','1042-30',
 '1045-00','1045-01','1045-02','1045-10','1045-18'].map(id=>'./original/OBS/'+id+'.png')]).concat(NATIVE_OBS_BULK_FILES.map(id=>'./original/OBS/bulk/'+id+'.png'));
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