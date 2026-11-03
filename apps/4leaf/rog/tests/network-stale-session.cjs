'use strict';
/* Deterministic signaling-race QA. Real two-browser WebRTC remains in network.cjs.
 * Simulate browser task ordering without ICE/STUN timing or a mocked match outcome.
 */
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');

(async()=>{
 const elements=new Map();
 const lobby={append(){},querySelector(){return null}};
 function element(id){
   if(!elements.has(id))elements.set(id,{
     id,value:'',textContent:'',disabled:false,className:'',
     classList:{toggle(){},add(){},remove(){}},
     addEventListener(){},closest(){return lobby},focus(){},select(){}
   });
   return elements.get(id);
 }
 const document={
   getElementById:element,readyState:'complete',
   createElement(){return {innerHTML:'',className:'',classList:{toggle(){}},append(){}}}
 };
 element('game-mode').value='network';
 const peers=[],commands=[],states=[];
 let delayNextOffer=false;
 class Peer {
   constructor(){
     this.iceGatheringState='complete';
     this.connectionState='new';
     this.channels=[];
     peers.push(this);
   }
   createDataChannel(){
     const ch={
       readyState:'connecting',sent:[],
       close(){this.readyState='closed'},
       send(message){this.sent.push(message)}
     };
     this.channels.push(ch);return ch;
   }
   createOffer(){
     if(delayNextOffer){
       delayNextOffer=false;
       return new Promise(resolve=>{this.releaseOffer=resolve});
     }
     return Promise.resolve({type:'offer',sdp:'v=0 offer-'+peers.length});
   }
   createAnswer(){return Promise.resolve({type:'answer',sdp:'v=0 answer-'+peers.length})}
   setLocalDescription(value){this.localDescription=value;return Promise.resolve()}
   setRemoteDescription(value){this.remoteDescription=value;return Promise.resolve()}
   close(){this.connectionState='closed'}
 }
 let redraws=0;
 const window={__ROG_TEST__:{drawGame:()=>{redraws++}},__LEAF_BRIDGE__:{
   getName:()=>'QA participant',getMatch:()=>null,
   remoteCommand:(...args)=>commands.push(args),
   receiveMatch:value=>states.push(value)
 }};
 const source=fs.readFileSync(path.join(__dirname,'../network.js'),'utf8');
 const run=new Function('window','document','RTCPeerConnection','navigator','btoa','atob',
   source+';return window.__LEAF_NET__;');
 const net=run(window,document,Peer,{},s=>'enc:'+s,s=>s.slice(4));

 await element('net-make').onclick();
 const oldPeer=peers.at(-1),old=oldPeer.channels[0];
 old.readyState='open';old.onopen();
 assert.equal(net.connected,true,'first WebRTC session opens');

 await element('net-make').onclick();
 const newPeer=peers.at(-1),current=newPeer.channels[0];
 current.readyState='open';current.onopen();
 assert.equal(net.connected,true,'replacement WebRTC session opens');
 const status=element('net-status').textContent;
 const newSessionRedraws=redraws;
 assert.ok(newSessionRedraws>=4,'opening and resetting sessions re-evaluates real match controls');

 // In a browser these callbacks can arrive AFTER the replacement onopen.
 old.onclose();old.onerror();
 old.onmessage({data:JSON.stringify({type:'command',action:'roll'})});
 oldPeer.connectionState='failed';oldPeer.onconnectionstatechange();
 assert.equal(net.connected,true,'old peer cannot disconnect the replacement');
 assert.equal(redraws,newSessionRedraws,'stale WebRTC events cannot repaint the current match controls');
 assert.equal(element('net-status').textContent,status,'old events cannot rewrite status');
 assert.equal(commands.length,0,'old channel cannot inject a gameplay command');

 current.onmessage({data:JSON.stringify({type:'command',action:'roll'})});
 assert.deepEqual(commands,[['roll',undefined,undefined]],
   'new connected host still accepts the authorized guest command');
 assert.equal(net.send({type:'chat',text:'hello'}),true);
 assert.equal(current.sent.at(-1),JSON.stringify({type:'chat',text:'hello'}));

 // Genuine WebRTC transitions can report 'disconnected' BEFORE onclose.
 // A still-open DataChannel must not authorize gameplay in that interval.
 const beforeDrop=redraws,commandCount=commands.length;
 newPeer.connectionState='disconnected';newPeer.onconnectionstatechange();
 assert.equal(net.connected,false,'temporary ICE disconnect must disable game turns');
 assert.equal(net.send({type:'chat',text:'offline'}),false,
  'disconnected ICE must not be treated as a usable chat/game transport');
 current.onmessage({data:JSON.stringify({type:'command',action:'roll'})});
 assert.equal(commands.length,commandCount,
  'stale open DataChannel cannot mutate host game while disconnected');
 assert.equal(redraws,beforeDrop+1,'ICE disconnect refreshes visible roll availability');
 const afterDrop=redraws;
 newPeer.connectionState='disconnected';newPeer.onconnectionstatechange();
 assert.equal(redraws,afterDrop,'repeated ICE disconnect must not repaint endlessly');
 // Transient disconnects sometimes recover on the same DataChannel.
 newPeer.connectionState='connected';newPeer.onconnectionstatechange();
 assert.equal(net.connected,true,'current ICE peer can recover on the same open channel');
 assert.equal(redraws,afterDrop+1,'recovery restores real game turn controls');
 assert.equal(net.send({type:'chat',text:'reconnected'}),true);
 current.onmessage({data:JSON.stringify({type:'command',action:'roll'})});
 assert.equal(commands.length,commandCount+1,'reconnected host accepts real guest commands');
 // Never re-enable a DataChannel that is already closed.
 newPeer.connectionState='disconnected';newPeer.onconnectionstatechange();
 current.readyState='closed';
 newPeer.connectionState='connected';newPeer.onconnectionstatechange();
 assert.equal(net.connected,false,'ICE connected alone cannot revive a closed DataChannel');
 current.readyState='open';
 newPeer.connectionState='connected';newPeer.onconnectionstatechange();
 assert.equal(net.connected,true,'only an open channel and current peer allow recovery');

 // If the first createOffer promise resolves last, it must not publish old SDP.
 delayNextOffer=true;
 const pending=element('net-make').onclick();
 await Promise.resolve();
 const delayedPeer=peers.at(-1);
 await element('net-make').onclick();
 const latestCode=element('net-output-offer').value;
 assert.ok(latestCode.includes('offer-'));
 delayedPeer.releaseOffer({type:'offer',sdp:'v=0 stale'});
 await pending;
 assert.equal(element('net-output-offer').value,latestCode,
   'stale ICE/signaling promise must not overwrite the latest invitation');

 // A delayed datachannel callback from an old guest peer must not take over.
 element('net-input-offer').value='enc:'+JSON.stringify({type:'offer',sdp:'v=0 remote'});
 await element('net-accept-offer').onclick();
 const previousGuest=peers.at(-1);
 await element('net-accept-offer').onclick();
 const liveGuest=peers.at(-1);
 const staleGuestChannel={readyState:'open',close(){},send(){}};
 previousGuest.ondatachannel({channel:staleGuestChannel});
 const liveGuestChannel={
   readyState:'open',sent:[],close(){},send(s){this.sent.push(s)}
 };
 liveGuest.ondatachannel({channel:liveGuestChannel});
 liveGuestChannel.onopen();
 assert.equal(net.connected,true);
 assert.equal(net.role,'guest');
 if(staleGuestChannel.onmessage){
   staleGuestChannel.onmessage({data:JSON.stringify({type:'state',match:{id:'stale'}})});
 }
 assert.equal(states.length,0,'old guest peer state is rejected');
 liveGuestChannel.onmessage({data:JSON.stringify({type:'state',match:{id:'current'}})});
 assert.deepEqual(states,[{id:'current'}],'new guest channel receives host state');

 const priorCloseRedraws=redraws;
 liveGuestChannel.onclose();
 assert.equal(redraws,priorCloseRedraws+1,'real channel close immediately refreshes disabled match controls');
 assert.equal(net.connected,false,'current session closing must disconnect');
 assert.equal(net.send({type:'chat',text:'too late'}),false,
   'no sends after current channel closes');
 console.log('WEBRTC STALE SESSION QA PASS: host/guest, events, commands, SDP, state and close');
})().catch(error=>{console.error('WEBRTC STALE SESSION QA FAIL',error.stack||error);process.exitCode=1});
