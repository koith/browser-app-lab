'use strict';
(function(){
 const $=id=>document.getElementById(id);
 const bridge=()=>window.__LEAF_BRIDGE__;
 const net={role:null,connected:false,guestName:null,send,transport:'webrtc-manual'};
 window.__LEAF_NET__=net;
 let peer=null,channel=null,outputOffer=null,outputAnswer=null,inputOffer=null,inputAnswer=null,state=null;
 const settings={iceServers:[{urls:'stun:stun.l.google.com:19302'},{urls:'stun:stun1.l.google.com:19302'}]};
 function notice(text,ok=false){if(state){state.textContent=text;state.className=ok?'net-status connected':'net-status'}}
 // Real match controls must reflect connection changes even if no turn redraw occurs.
 function refreshTurnControls(){window.__ROG_TEST__?.drawGame?.()}
 function encode(data){return btoa(JSON.stringify(data))}
 function decode(value,type){let result;try{result=JSON.parse(atob(value.replace(/\s/g,'')))}catch{throw Error('코드 형식이 올바르지 않습니다.')}if(result?.type!==type||typeof result.sdp!=='string'||!result.sdp.startsWith('v=0')||result.sdp.length>85000)throw Error('다른 연결 코드가 입력됐습니다.');return result}
 async function gather(pc){if(pc.iceGatheringState==='complete')return;await new Promise(resolve=>{let timer;const finish=()=>{clearTimeout(timer);pc.removeEventListener('icegatheringstatechange',check);resolve()};const check=()=>{if(pc.iceGatheringState==='complete')finish()};pc.addEventListener('icegatheringstatechange',check);timer=setTimeout(finish,10500)})}
 function send(data){if(!net.connected||channel?.readyState!=='open')return false;try{channel.send(JSON.stringify(data));return true}catch{return false}}
 function reset(){
   net.connected=false;net.role=null;net.guestName=null;
   // Do not retain a host-only broadcast callback across a new peer session.
   // A later guest connection must never inherit old host authority.
   if(bridge())bridge().onState=null;
   try{channel?.close()}catch{}try{peer?.close()}catch{}
   channel=null;peer=null;refreshTurnControls();
 }
 function openPeer(role){
   if(typeof RTCPeerConnection==='undefined')throw Error('이 WebView는 WebRTC 통신을 지원하지 않습니다.');
   reset();net.role=role;
   const pc=new RTCPeerConnection(settings);
   peer=pc;
   // A delayed event from a closed RTCPeerConnection cannot take over a newer session.
   pc.ondatachannel=e=>{if(peer===pc&&net.role==='guest')attach(e.channel)};
   pc.onconnectionstatechange=()=>{
     if(peer!==pc)return;
     const status=pc.connectionState;
     // A WebRTC DataChannel may remain in 'open' while ICE connectivity is
     // disconnected. Pause game commands immediately, not only on 'failed'.
     if(['disconnected','failed','closed'].includes(status)){
       if(net.connected){net.connected=false;refreshTurnControls()}
       notice(status==='disconnected'
        ?'직접 연결이 일시적으로 끊어졌습니다. 상대와 다시 연결되면 턴을 진행할 수 있습니다.'
        :'직접 연결 실패: 양쪽 네트워크 또는 방화벽을 확인하세요.');
     }else if(status==='connected'&&channel?.readyState==='open'&&!net.connected){
       // An ICE interruption can recover without another DataChannel open.
       // Re-enable actions only for this exact current peer and open channel.
       net.connected=true;
       refreshTurnControls();
       notice('상대와 다시 연결되었습니다.',true);
       if(net.role==='host'&&bridge()?.getMatch?.()?.mode==='network')
         send({type:'state',match:bridge().getMatch()});
       else if(net.role==='guest')
         send({type:'hello',name:bridge()?.getName?.()||'Guest'});
     }
   };
   return pc;
 }
 // The peer is allowed to send a battle dialog, not arbitrary JSON that
 // crashes the receiver or creates thousands of UI controls. Validate the
 // actual host-produced protocol shape before touching the current modal.
 function validBattleRequest(data){
   const dice=a=>Array.isArray(a)&&a.length<=32&&
    a.every(v=>Number.isInteger(v)&&v>=1&&v<=6);
   return Number.isSafeInteger(data.bid)&&data.bid>0&&
    typeof data.attacker==='string'&&data.attacker.length<=80&&
    typeof data.defender==='string'&&data.defender.length<=80&&
    Number.isFinite(data.attack)&&Number.isFinite(data.defense)&&
    dice(data.diceAttack)&&dice(data.diceDefense)&&
    Array.isArray(data.options)&&data.options.length>=1&&
    data.options.length<=9&&data.options.every(v=>
     typeof v==='string'&&v.length>0&&v.length<=100);
 }
 function attach(ch){
   channel=ch;
   const isCurrent=()=>channel===ch;
   channel.onopen=()=>{
     if(!isCurrent())return;
     net.connected=true;if(net.role==='host'&&bridge())bridge().onState=m=>send({type:'state',match:m});refreshTurnControls();notice(net.role==='host'?'연결 완료! 아래 게임 시작으로 2인 대전을 열 수 있습니다.':'연결 완료! 호스트가 경기를 시작하면 자동으로 입장합니다.',true);
     send({type:'hello',name:bridge()?.getName?.()||'Guest'});
     if(net.role==='host'&&bridge()?.getMatch?.()?.mode==='network')send({type:'state',match:bridge().getMatch()});
   };
   channel.onclose=()=>{
     if(!isCurrent())return;
     net.connected=false;
     refreshTurnControls();
     notice('상대와 연결이 끊어졌습니다. 다시 초대를 생성하세요.');
   };
   channel.onerror=()=>{if(isCurrent())notice('통신 오류. 연결 코드를 재발급하세요.')};
   channel.onmessage=e=>{
     if(!isCurrent()||!net.connected||ch.readyState!=='open')return;
     if(typeof e.data!=='string'||e.data.length>150000)return;
     let data;try{data=JSON.parse(e.data)}catch{return}
     if(!data||typeof data!=='object')return;
     if(data.type==='hello'&&net.role==='host'){
       net.guestName=String(data.name||'플레이어 2').slice(0,12);
       bridge()?.setGuestName?.(net.guestName);
       if(bridge()?.getMatch?.()?.mode==='network')send({type:'state',match:bridge().getMatch()});
     }else if(data.type==='state'&&net.role==='guest'){
       // A connected DataChannel does not prove the other device has
       // accepted a state. Surface the result of the guest's durable-save
       // gate to the host instead of silently leaving the two games apart.
       const accepted=bridge()?.receiveMatch?.(data.match)===true;
       send({type:accepted?'state-accepted':'state-rejected'});
     }else if(data.type==='state-rejected'&&net.role==='host'){
       notice('상대 기기에서 경기 상태를 적용하지 못했습니다. 상대방의 저장 공간과 경기 상태를 확인한 후 다시 연결하세요.');
     }else if(data.type==='state-accepted'&&net.role==='host'){
       notice('상대 기기에서 전달받은 경기 상태를 저장했습니다.',true);
     }else if(data.type==='command'&&net.role==='host'&&['roll','item','ability'].includes(data.action)){
       bridge()?.remoteCommand?.(data.action,data.index,data.steps);
     }else if(data.type==='battle-request'&&net.role==='guest'){
       const modal=$('modal'),title=$('modal-title'),body=$('modal-content'),buttons=$('modal-buttons');
       if(!modal||!validBattleRequest(data))return;
       title.textContent='⚔ 전투 카드 선택 · '+String(data.attacker).slice(0,16)+' VS '+String(data.defender).slice(0,16);
       body.replaceChildren();
       const p=document.createElement('p');p.textContent='공격 '+data.attack+' / 방어 '+data.defense+' · '+(data.diceAttack||[]).join(',')+' : '+(data.diceDefense||[]).join(',');body.append(p);
       buttons.replaceChildren();
       data.options.filter(x=>typeof x==='string').slice(0,9).forEach(label=>{
         const button=document.createElement('button');button.textContent=label;
         button.onclick=()=>{
           modal.classList.add('hidden');modal.classList.remove('battle-present');
           send({type:'battle-choice',bid:data.bid,label});
         };
         buttons.append(button);
       });
       modal.classList.remove('hidden');
     }else if(data.type==='battle-choice'&&net.role==='host'){
       bridge()?.remoteBattleChoice?.(data.bid,data.label);
     }else if(data.type==='chat'&&typeof data.text==='string'){
       const div=document.createElement('div'),b=document.createElement('b');
       b.textContent=String(data.who||'상대').slice(0,12)+'　';
       div.append(b,document.createTextNode(data.text.slice(0,250)));
       if(window.__LEAF_CHAT_APPEND__)window.__LEAF_CHAT_APPEND__($('chat-log'),div,90);
       else{$('chat-log').append(div);$('chat-log').scrollTop=$('chat-log').scrollHeight}
     }
   };
 }
 async function makeOffer(){
   notice('초대 코드 생성 중…');
   outputOffer.value='';
   let pc=null;
   try{
     pc=openPeer('host');attach(pc.createDataChannel('4leaf',{ordered:true}));
     const offer=await pc.createOffer();
     if(peer!==pc)return;
     await pc.setLocalDescription(offer);
     if(peer!==pc)return;
     await gather(pc);
     if(peer!==pc)return;
     outputOffer.value=encode({type:'offer',sdp:pc.localDescription.sdp});
     notice('초대 코드를 상대 기기에 전달하고, 받은 응답 코드를 아래에 붙여넣으세요.');
   }catch(e){if(!pc||peer===pc)notice('초대 실패: '+e.message)}
 }
 async function makeAnswer(){
   notice('초대를 수락하는 중…');
   outputAnswer.value='';
   let pc=null;
   try{
     const data=decode(inputOffer.value,'offer');
     pc=openPeer('guest');
     await pc.setRemoteDescription({type:'offer',sdp:data.sdp});
     if(peer!==pc)return;
     const answer=await pc.createAnswer();
     if(peer!==pc)return;
     await pc.setLocalDescription(answer);
     if(peer!==pc)return;
     await gather(pc);
     if(peer!==pc)return;
     outputAnswer.value=encode({type:'answer',sdp:pc.localDescription.sdp});
     notice('생성된 응답 코드를 호스트 기기로 보내세요.');
   }catch(e){if(!pc||peer===pc)notice('초대 수락 실패: '+e.message)}
 }
 async function acceptAnswer(){
   notice('두 기기를 연결하는 중…');
   const pc=peer;
   try{
     if(!pc||net.role!=='host')throw Error('호스트 초대를 먼저 생성하세요.');
     const data=decode(inputAnswer.value,'answer');
     if(peer!==pc)return;
     await pc.setRemoteDescription({type:'answer',sdp:data.sdp});
     if(peer!==pc)return;
     notice('P2P 연결을 확인 중입니다…');
   }catch(e){if(!pc||peer===pc)notice('연결 실패: '+e.message)}
 }
 async function copy(box){try{await navigator.clipboard.writeText(box.value);notice('코드를 복사했습니다.')}catch{box.focus();box.select();notice('코드를 선택했습니다. 직접 복사해 주세요.')}}
 function init(){
   const mode=$('game-mode'),lobby=mode?.closest('.lobby-config');if(!lobby)return;
   const panel=document.createElement('section');panel.id='net-panel';panel.className='net-panel hidden';
   panel.innerHTML=[
     '<h4>♧ 실제 기기 간 WebRTC 2인 대전</h4>',
     '<p>원작 서버와 무관한 직접 연결입니다. 양쪽 기기에서 초대·응답 코드를 한 번씩 교환하세요. 일부 모바일망·방화벽에서는 연결이 실패할 수 있습니다.</p>',
     '<div class="net-actions"><button id="net-make">① 호스트 초대 만들기</button><button id="net-accept-offer">② 상대 초대 수락</button></div>',
     '<label>내 초대 코드<textarea id="net-output-offer" rows="2" readonly></textarea></label>',
     '<button id="net-copy-offer" class="net-copy">초대 코드 복사</button>',
     '<label>받은 초대 코드<textarea id="net-input-offer" rows="2" placeholder="초대 코드를 붙여넣으세요"></textarea></label>',
     '<label>내 응답 코드<textarea id="net-output-answer" rows="2" readonly></textarea></label>',
     '<button id="net-copy-answer" class="net-copy">응답 코드 복사</button>',
     '<label>받은 응답 코드<textarea id="net-input-answer" rows="2" placeholder="상대 응답을 붙여넣으세요"></textarea></label>',
     '<button id="net-apply-answer">③ 호스트가 응답 연결</button>',
     '<p id="net-status" role="status" class="net-status">직접 대전 모드입니다.</p>'
   ].join('');
   lobby.append(panel);
   state=$('net-status');outputOffer=$('net-output-offer');outputAnswer=$('net-output-answer');
   inputOffer=$('net-input-offer');inputAnswer=$('net-input-answer');
   $('net-make').onclick=makeOffer;$('net-accept-offer').onclick=makeAnswer;
   $('net-apply-answer').onclick=acceptAnswer;
   $('net-copy-offer').onclick=()=>copy(outputOffer);$('net-copy-answer').onclick=()=>copy(outputAnswer);
   const update=()=>{
     const show=mode.value==='network';
     panel.classList.toggle('hidden',!show);
     $('bot-count').disabled=show;
     if(show)$('bot-count').value='1';
     const note=lobby.querySelector('.fine');
     if(note)note.textContent=({ai:'컴퓨터 대전',hotseat:'같은 기기에서 번갈아 플레이',network:'두 기기 간 WebRTC 직접 연결'})[mode.value]+' · 원본 소스 리소스를 활용한 복원 개발판입니다.';
   };
   mode.addEventListener('change',update);update();
 }
 if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',init);else init();
})();