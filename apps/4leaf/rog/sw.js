'use strict';
const REVISION='4leaf-revival-pwa-v85';
// 32 genuinely archived 145×97 original TIS platform images. First offline
// Genesis match must draw the same extracted raised platforms, not replace
// uncached native source art with a CSS placeholder on first room entry.
const NATIVE_OBS_BULK_FILES='1040-00 1040-01 1040-02 1040-03 1040-10 1040-18 1040-25 1040-30 1043-00 1043-01 1043-02 1043-03 1043-10 1043-18 1043-25 1043-30 1044-00 1044-01 1044-02 1044-03 1044-10 1044-18 1044-25 1044-30 1046-00 1046-01 1046-02 1046-03 1046-10 1046-18 1046-25 1046-30 1047-00 1047-01 1047-02 1047-03 1047-10 1047-18 1047-25 1047-30 1048-00 1048-01 1048-02 1048-03 1048-10 1048-18 1048-25 1048-30 1049-00 1049-01 1049-02 1049-03 1049-10 1049-18 1049-25 1049-30 1050-00 1050-01 1050-02 1050-03 1050-10 1050-18 1050-25 1050-30 1051-00 1051-01 1051-02 1051-03 1051-10 1051-18 1051-25 1051-30 1052-00 1052-01 1052-02 1052-03 1052-10 1052-18 1052-25 1052-30 1053-00 1053-01 1053-02 1053-03 1053-10 1053-18 1053-25 1053-30 1054-00 1054-01 1054-02 1054-03 1054-10 1054-18 1054-25 1054-30 1055-00 1055-01 1055-02 1055-03 1055-10 1055-18 1055-25 1055-30 1056-00 1056-01 1056-02 1056-03 1056-10 1056-18 1056-25 1056-30 1058-00 1058-01 1058-02 1058-03 1058-10 1058-18 1058-25 1058-30 1059-00 1059-01 1059-02 1059-03 1059-10 1059-18 1059-25 1059-30 1060-00 1060-01 1060-02 1060-03 1060-10 1060-18 1060-25 1060-30 1061-00 1061-01 1061-02 1061-03 1061-10 1061-18 1061-25 1061-30 1062-00 1062-01 1062-02 1062-03 1062-10 1062-18 1062-25 1062-30 1063-00 1063-01 1063-02 1063-03 1063-10 1063-18 1063-25 1063-30 1064-00 1064-01 1064-02 1064-03 1064-10 1064-18 1064-25 1064-30 1065-00 1065-01 1065-02 1065-03 1065-10 1065-18 1065-25 1065-30 1066-00 1066-01 1066-02 1066-03 1066-10 1066-18 1066-25 1066-30 1067-00 1067-01 1067-02 1067-03 1067-10 1067-18 1067-25 1067-30 1068-00 1068-01 1068-02 1068-03 1068-10 1068-18 1068-25 1068-30 1069-00 1069-01 1069-02 1069-03 1069-10 1069-18 1069-25 1069-30 1070-00 1070-01 1070-02 1070-03 1070-10 1070-18 1070-25 1070-30 1071-00 1071-01 1071-02 1071-03 1071-10 1071-18 1071-25 1071-30 1072-00 1072-01 1072-02 1072-03 1072-10 1072-18 1072-25 1072-30 1073-00 1073-01 1073-02 1073-03 1073-10 1073-18 1073-25 1073-30 1074-00 1074-01 1074-02 1074-03 1074-10 1074-18 1074-25 1074-30 1075-00 1075-01 1075-02 1075-03 1075-10 1075-18 1075-25 1075-30 1076-00 1076-01 1076-02 1076-03 1076-10 1076-18 1076-25 1076-30 1077-00 1077-01 1077-02 1077-03 1077-10 1077-18 1077-25 1077-30 1078-00 1078-01 1078-02 1078-03 1078-10 1078-18 1078-25 1078-30 1079-00 1079-01 1079-02 1079-03 1079-10 1079-18 1079-25 1079-30 1080-00 1080-01 1080-02 1080-03 1080-10 1080-18 1080-25 1080-30 1081-00 1081-01 1081-02 1081-03 1081-10 1081-18 1081-25 1081-30 1082-00 1082-01 1082-02 1082-03 1082-10 1082-18 1082-25 1082-30 1083-00 1083-01 1083-02 1083-03 1083-10 1083-18 1083-25 1083-30 1084-00 1084-01 1084-02 1084-03 1084-10 1084-18 1084-25 1084-30 1085-00 1085-01 1085-02 1085-03 1085-10 1085-18 1085-25 1085-30 1086-00 1086-01 1086-02 1086-03 1086-10 1086-18 1086-25 1086-30 1087-00 1087-01 1087-02 1087-03 1087-10 1088-00 1088-01 1088-02 1088-03 1088-10 1088-18 1088-25 1088-30 1089-00 1089-01 1089-02 1089-03 1089-10 1090-00 1090-01 1090-02 1090-03 1090-10 1090-18 1090-25 1090-30 1092-00 1092-01 1092-02 1092-03 1094-00 1094-01 1094-02 1094-03 1094-10 1096-00 1096-01 1096-02 1097-00 1097-01 1097-02 1097-03 1099-00 1099-01 1099-02 1099-03 1099-10 1100-00 1100-01 1100-02 1100-03 1100-10 1125-00 1125-01 1125-02 1125-03 1125-10 1127-00 1127-01 1127-02 1127-03 1127-10 1127-18 1127-25 1130-00 1130-01 1130-02 1130-03 1130-10 1130-18 1130-25 1131-00 1131-01 1131-02 1131-03 1131-10 1131-18 1131-25 1133-00 1133-01 1133-02 1133-03 1133-10 1133-18 1134-00 1134-01 1134-02 1134-03 1134-10 1134-18 1135-00 1135-01 1135-02 1135-03 1135-10 1135-18 1135-25 1136-00 1136-01 1136-02 1136-03 1137-00 1137-01 1137-02 1137-03 1138-00 1138-01 1138-02 1138-03 1139-00 1139-01 1139-02 1139-03 1140-00 1140-01 1140-02 1140-03 1140-10 1140-18 1140-25 1140-30 1141-00 1141-01 1141-02 1141-03 1141-10 1141-18 1142-00 1142-01 1142-02 1142-03 1142-10 1142-18 1143-00 1143-01 1143-02 1143-03 1143-10 1143-18 1143-25 1143-30 1144-00 1144-01 1144-02 1144-03 1144-10 1144-18 1144-25 1144-30 1145-00 1145-01 1145-02 1145-03 1145-10 1145-18 1146-00 1146-01 1146-02 1146-03 1147-00 1147-01 1147-02 1147-03 1147-10 1147-18 1156-00 1156-01 1156-02 1156-03 1156-10 1156-18 1156-25 1156-30 1158-00 1158-01 1158-02 1158-03 1158-10 1158-18 1158-25 1158-30 1160-00 1160-01 1160-02 1160-03 1160-10 1160-18 1161-00 1161-01 1161-02 1161-03 1161-10 1161-18 1162-00 1162-01 1162-02 1162-03 1162-10 1162-18 1162-25 1162-30 1163-00 1163-01 1163-02 1163-03 1163-10 1163-18 1164-00 1164-01 1164-02 1164-03 1165-00 1165-01 1165-02 1165-03 1166-00 1166-01 1166-02 1166-03 1166-10 1166-18 1166-25 1166-30 1167-00 1167-01 1167-02 1167-03 1167-10 1167-18 1169-00 1169-01 1169-02 1169-03 1169-10 1169-18 1169-25 1169-30 1170-00 1170-01 1170-02 1170-03 1171-00 1171-01 1171-02 1171-03 1171-10 1171-18 1171-25'.split(' ');
const ORIGINAL_SOURCE_SPR_FILES='roll-00 roll-01 roll-02 roll-03 eventRoll1-00 eventRoll1-01 eventRoll1-02 eventRoll1-03 eventRoll1-04 eventRoll1-05 eventRoll1-06 eventRoll1-07 eventRoll1-08 eventRoll1-09 eventRoll1-10 eventRoll1-11 eventRoll1-12 eventRoll1-13 eventRoll1-14 eventRoll1-15'.split(' ');
const NATIVE_TIS_FILES='0000 0001 0006 0007 0008 0009 0010 0011 0012 0013 0014 0015 0016 0017 0018 0019 0020 0021 0022 0023 0024 0025 0026 0027 0028 0029 0030 0031 0035 0041 0043 0046'.split(' ');
const CORE=['./','./index.html','./app-version.json','./pwa-runtime.js','./manifest.webmanifest','./icon.svg','./game.js','./style.css','./world-perspective.css','./original-tiles.css','./original.css','./lobby.css','./game-authentic.css','./network.css','./network.js','./original-shell-accurate.css','./mainframe-native-toolbar.css','./original/MainFrame/toolbarbtn.png','./original/MainFrame/pannel.png','./shop-native.js','./cardshop-native-controls.css','./cardshop-original-2003.css','./cardshop-native-controls.js','./original/CardShop/cardshopbutton.png','./dice-native-stage.js','./dice-native-stage.css','./dice-native-map-buttons.css','./dice-native-map-buttons.js','./dice-native-room-buttons.js','./dice-native-room-buttons.css','./original/Room/roombutton.png','./original/Map/mapbutton.png','./original/Map/maplist.png','./town-native-room-hotspots.css','./native-chattown-scale.css','./knighttown-native.js','./knighttown-native.css','./original/KnightTown/knightback.png','./original/KnightTown/sea01.png','./original/KnightTown/sea02.png','./original/KnightTown/sea03.png','./original/KnightTown/snow01.png','./original/KnightTown/plain01.png','./original/KnightTown/plain02.png','./original-chat-input.css','./chatroom-native-exit.css','./chatroom-native-exit.js','./chatroom-native-talkbox.css','./chatroom-native-talkbox.js','./dice-native-player-portraits.css','./original/IMG/avatarback.png','./dice-native-chessmen-hud.css','./dice-original-selector.css','./dice-native-menu-chrome.css','./dice-native-dialog-event.css','./original/IMG/dialog.png','./original/IMG/eventmsgbox.png','./original/IMG/menu.png','./original/MainFrame/toolbarbtn.png','./board-camera.js','./dice-dmp-camera-controls.css','./dice-source-dmp-terrain-explorer.js','./dice-source-dmp-terrain-explorer.css','./dice-native-tis-clean.css','./dice-native-battle-podium.css','./dice-native-battle-dice.css','./dice-2004-full-frame.css','./dice-source-roll.css','./dice-source-roll.js','./dice-source-native-ui.css','./dice-source-native-chat-scroll.js','./original/IMG/okcancelbut.png','./original/IMG/scrollbutton.png','./original/IMG/stats.png','./dice-fall.js','./dice-fall.css','./genesis-chessman-actors.js','./registry-native-chroma.js','./genesis-chessman-actors.css','./original/IMG/selector.png','./original/CardData/chm_12.png','./original/CardData/chm_33.png','./original/CardData/chm_8.png','./chatroom-native-panels.css','./chatroom-native-2004-frame.css','./chatroom-native-ringbtn.css','./chatroom-native-scrollbar.css','./chatroom-native-scrollbar.js','./original/ChatRoom/scrollbar.png','./original/ChatRoom/ringbtn.png','./chatroom-native-panels.js','./chatroom-native-owner-dialog.js','./chatroom-native-owner-dialog.css','./registry-native-avatar-dialog.js','./registry-native-avatar-dialog.css','./original/Registry/avatardialog1.png','./original/Registry/avatardialog2.png','./original/Registry/avatardialog3.png','./chatroom-native-expressions.js','./chatroom-native-expressions.css','./original/ChatRoom/expdialogbtn.png','./original/ChatRoom/ownerdialog.png','./original/ChatRoom/talkbox.png','./original/ChatRoom/exitbtn.png','./original-world-notice.css','./original/WorldMap/notice.png','./original/ChatRoom/chatbaredit.png','./original/Map/mapback.png','./original/Room/roomback.png','./original/MainFrame/title.png','./original/MainFrame/borderbtn.png','./original/CardShop/cardshopback.png','./central-client.js','./world-map.js','./world-social.css','./world-map-source-moon.css','./social-chat.js','./lobby-ui.js','./original/maps.js','./original/tiles.js','./original/chessmen.js','./original/Gif/d1lobby.png','./original/Gif/d1waitroom.png','./original/WorldMap/worldmapback.png','./original/CardShop/cardshopback.png','./original/IMG/bgtile.png','./dice-native-client-frame.css','./dice-native-minimap-navigation.css','./dice-native-client-frame.js','./original/IMG/chatwnd.png','./original/IMG/abilitybar.png','./original/IMG/topbar.png','./original/IMG/minimap.png','./original/WorldMap/mainstreet.png','./original/WorldMap/knights.png','./original/WorldMap/northchatrgn.png','./original/WorldMap/southchatrgn.png','./original/WorldMap/dice.png','./original/WorldMap/m4leaf.png','./original/ChatTown/northback.png','./original/ChatTown/southback.png','./original/ChatTown/plainbtn.png','./original/ChatTown/seabtn.png','./original/ChatTown/snowbtn.png','./original/ChatRoom/room0.png','./original/ChatRoom/room1.png','./original/ChatRoom/room2.png','./original/ChatRoom/room3.png','./original/ChatRoom/room4.png','./original/ChatRoom/room5.png','./original/ChatRoom/room3t.png','./original/ChatRoom/room4t.png','./original/ChatRoom/room5t.png','./original/Registry/sava00.png','./original/Registry/sava82.png','./original/Registry/sava06.png','./original/Registry/sava01.png','./original/Registry/sava85.png','./original/Registry/sava02.png','./original/Registry/sava84.png','./original/Registry/sava04.png','./original/Registry/sava03.png','./original/Registry/sava83.png','./original/Registry/sava05.png','./original/Registry/sava86.png','./mainframe-native-snapshot.js','./mainframe-native-snapshot.css','./original/MainFrame/snaplogo.png','./original/MainFrame/snapnumber.png','./original/MainFrame/wallpaper.png','./dice-native-tis-depth.css','./dice-native-tis-orientation.css','./dice-ai-autoplay.css','./dice-native-pawn-dmp-depth.css','./dice-native-tis-alpha.js'].concat(
 NATIVE_TIS_FILES.map(name=>'./original/Tiles/'+name+'.png')
).concat(['./original/OBS/animation-manifest.js','./original/OBS/animation-extra.js','./dice-original-obs.css','./dice-native-battle-source-spr.css','./dice-native-source-events.js','./dice-native-minipanel-spr.js','./dice-native-minipanel-spr.css','./dice-original-ability-spr.js','./dice-original-ability-spr.css','./dice-native-source-events.css',
 './dice-source-tile-pitch.css','./dice-d4-source-fallback.css',
 './dice-source-chessman-battle.css',
 ...['1042-00','1042-01','1042-02','1042-03','1042-10','1042-18','1042-25','1042-30',
 '1045-00','1045-01','1045-02','1045-10','1045-18'].map(id=>'./original/OBS/'+id+'.png')]).concat(NATIVE_OBS_BULK_FILES.map(id=>'./original/OBS/bulk/'+id+'.png')).concat(ORIGINAL_SOURCE_SPR_FILES.map(id=>'./original/SourceSPR/'+id+'.png'))
 .concat(['./original/SourceSPRExtra/manifest.json',
  './original/SourceSPRExtra/winBattle-00.png',
  './original/SourceSPRExtra/winBattle-01.png',
  './original/SourceSPRExtra/winAbility-00.png',
  './original/SourceSPRExtra/winAbility-01.png',
  './original/SourceSPRExtra/winAbility-02.png',
  './original/SourceSPRExtra/winAbility-03.png',
  './original/SourceSPRExtra/winAbility-04.png',
  './original/SourceSPRExtra/winAbility-05.png',
  './original/SourceSPRExtra/winJail-00.png','./original/SourceSPRExtra/winDoa-00.png','./original/SourceSPRExtra/minipanel-00.png','./original/SourceSPRExtra/minipanel-01.png','./original/SourceSPRExtra/minipanel-02.png','./original/SourceSPRExtra/minipanel-03.png',
  './original/SourceSPRExtra/winResult-00.png']);
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