'use strict';
(function(){
 const $=id=>document.getElementById(id);
 const bridge=()=>window.__LEAF_BRIDGE__;
 const net={role:null,connected:false,guestName:null,send,transport:'webrtc-manual'};
 window.__LEAF_NET__=net;
 let peer=null,channel=null,outputOffer=null,outputAnswer=null,inputOffer=null,inputAnswer=null,state=null;
 const settings={iceServers:[{urls:'stun:stun.l.google.com:19302'},{urls:'stun:stun1.l.google.com:19302'}]};
 function notice(text,ok=false){if(state){state.textContent=text;state.className=ok?'net-status connected':'net-status'}}
 function encode(data){return btoa(JSON.stringify(data))}
 function decode(value,type){let result;try{result=JSON.parse(atob(value.replace(/\s/g,'')))}catch{throw Error('코드 형식이 올바르지 않습니다.')}if(result?.type!==type||typeof result.sdp!=='string'||!result.sdp.startsWith('v=0')||result.sdp.length>85000)throw Error('다른 연결 코드가 입력됐습니다.');return result}
 async function gather(pc){if(pc.iceGatheringState==='complete')return;await new Promise(resolve=>{let timer;const finish=()=>{clearTimeout(timer);pc.removeEventListener('icegatheringstatechange',check);resolve()};const check=()=>{if(pc.iceGatheringState==='complete')finish()};pc.addEventListener('icegatheringstatechange',check);timer=setTimeout(finish,10500)})}
 function send(data){if(!net.connected||channel?.readyState!=='open')return false;try{channel.send(JSON.stringify(data));return true}catch{return false}}
 function reset(){net.connected=false;net.role=null;try{channel?.close()}catch{}try{peer?.close()}catch{}channel=null;peer=null}
 function openPeer(role){
   if(typeof RTCPeerConnection==='undefined')throw Error('이 WebView는 WebRTC 통신을 지원하지 않습니다.');
   reset();net.role=role;peer=new RTCPeerConnection(settings);
   peer.ondatachannel=e=>{if(net.role==='guest')attach(e.channel)};
   peer.onconnectionstatechange=()=>{if(peer&&peer.connectionState==='failed'){net.connected=false;notice('직접 연결 실패: 양쪽 네트워크 또는 방화벽을 확인하세요.')}};
   return peer;
 }
 function attach(ch){
   channel=ch;
   channel.onopen=()=>{
     net.connected=true;notice(net.role==='host'?'연결 완료! 아래 게임 시작으로 2인 대전을 열 수 있습니다.':'연결 완료! 호스트가 경기를 시작하면 자동으로 입장합니다.',true);
     send({type:'hello',name:bridge()?.getName?.()||'Guest'});
     if(net.role==='host'&&bridge()?.getMatch?.()?.mode==='network')send({type:'state',match:bridge().getMatch()});
   };
   channel.onclose=()=>{net.connected=false;notice('상대와 연결이 끊어졌습니다. 다시 초대를 생성하세요.')};
   channel.onerror=()=>notice('통신 오류. 연결 코드를 재발급하세요.');
   channel.onmessage=e=>{
     if(typeof e.data!=='string'||e.data.length>150000)return;
     let data;try{data=JSON.parse(e.data)}catch{return}
     if(!data||typeof data!=='object')return;
     if(data.type==='hello'&&net.role==='host'){
       net.guestName=String(data.name||'플레이어 2').slice(0,12);
       bridge()?.setGuestName?.(net.guestName);
       if(bridge()?.getMatch?.()?.mode==='network')send({type:'state',match:bridge().getMatch()});
     }else if(data.type==='state'&&net.role==='guest'){
       bridge()?.receiveMatch?.(data.match);
     }else if(data.type==='command'&&net.role==='host'&&data.action==='roll'){
       bridge()?.remoteRoll?.();
     }else if(data.type==='chat'&&typeof data.text==='string'){
       const div=document.createElement('div'),b=document.createElement('b');
       b.textContent=String(data.who||'상대').slice(0,12)+'　';
       div.append(b,document.createTextNode(data.text.slice(0,250)));
       $('chat-log').append(div);$('chat-log').scrollTop=$('chat-log').scrollHeight;
     }
   };
 }
 async function makeOffer(){
   notice('초대 코드 생성 중…');
   try{
     const pc=openPeer('host');attach(pc.createDataChannel('4leaf',{ordered:true}));
     await pc.setLocalDescription(await pc.createOffer());await gather(pc);
     outputOffer.value=encode({type:'offer',sdp:pc.localDescription.sdp});
     notice('초대 코드를 상대 기기에 전달하고, 받은 응답 코드를 아래에 붙여넣으세요.');
   }catch(e){notice('초대 실패: '+e.message)}
 }
 async function makeAnswer(){
   notice('초대를 수락하는 중…');
   try{
     const data=decode(inputOffer.value,'offer'),pc=openPeer('guest');
     await pc.setRemoteDescription({type:'offer',sdp:data.sdp});
     await pc.setLocalDescription(await pc.createAnswer());await gather(pc);
     outputAnswer.value=encode({type:'answer',sdp:pc.localDescription.sdp});
     notice('생성된 응답 코드를 호스트 기기로 보내세요.');
   }catch(e){notice('초대 수락 실패: '+e.message)}
 }
 async function acceptAnswer(){
   notice('두 기기를 연결하는 중…');
   try{
     if(!peer||net.role!=='host')throw Error('호스트 초대를 먼저 생성하세요.');
     const data=decode(inputAnswer.value,'answer');
     await peer.setRemoteDescription({type:'answer',sdp:data.sdp});
     notice('P2P 연결을 확인 중입니다…');
   }catch(e){notice('연결 실패: '+e.message)}
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