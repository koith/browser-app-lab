export function selectLocalTurkishVoice(voices){return voices.find(v=>v.localService===true&&v.lang.toLowerCase().replace("_","-")==="tr-tr")||voices.find(v=>v.localService===true&&/^tr(?:-|$)/i.test(v.lang.replace("_","-")))||null;}

export function findAudio(manifest,targetId,text,{preview=false}={}){if(manifest?.schemaVersion!=="1.0.0"||typeof text!=="string")return null;return manifest.assets.find(a=>a.targetId===targetId&&a.text===text.normalize("NFC")&&a.locale==="tr-TR"&&(preview||["audio_reviewed","release_ready","published"].includes(a.reviewStatus))&&/^assets\/audio\/[A-Za-z0-9/_-]+\.mp3$/.test(a.path)&&/^[a-f0-9]{64}$/.test(a.sha256))||null;}

export function createAudioSession({manifest,baseURL,env=globalThis,preview=false,onStatus=()=>{}}){
 let playing=null,recording=null,stream=null,recordURL=null,pending=false,epoch=0,disposed=false;
 const status=(kind,detail)=>onStatus({kind,detail}),stopTracks=()=>{stream?.getTracks().forEach(t=>t.stop());stream=null;};
 function stopPlayback(){if(playing){playing.pause();playing.removeAttribute("src");playing.load();playing=null;}env.speechSynthesis?.cancel();}
 async function play(targetId,text,{rate=1,repeat=false,useDevice=false}={}){
  if(disposed||pending||recording)throw Error("Recording or disposed");
  if(!Number.isFinite(rate)||rate<0.6||rate>1.25)throw Error("Invalid rate");
  stopPlayback();const asset=findAudio(manifest,targetId,text,{preview});
  if(asset&&!useDevice){const a=new env.Audio(new env.URL(asset.path,baseURL).href);playing=a;a.playbackRate=rate;a.loop=Boolean(repeat);
   a.addEventListener("ended",()=>{if(playing===a)status("ended","fixed");});a.addEventListener("error",()=>{if(playing===a)status("error","fixed-file-unavailable");});
   try{await a.play();if(playing===a)status("playing",preview?"fixed-preview":"fixed");return "fixed";}catch(e){if(playing===a){stopPlayback();status("error",e.message);}throw e;}}
  const synth=env.speechSynthesis,voice=selectLocalTurkishVoice(synth?.getVoices()||[]);
  if(!preview||!voice||!env.SpeechSynthesisUtterance){status("unavailable","unapproved-or-no-local-tr");return "unavailable";}
  const u=new env.SpeechSynthesisUtterance(text);u.voice=voice;u.lang="tr-TR";u.rate=rate;u.onend=()=>status("ended","device-preview");u.onerror=e=>status("error",e.error||"tts");synth.speak(u);status("playing","device-preview");return "device";
 }
 function releaseRecording(){if(recordURL){env.URL.revokeObjectURL(recordURL);recordURL=null;}}
 async function startRecording(){if(disposed||recording||pending)throw Error("Already recording or disposed");if(!env.isSecureContext||!env.navigator?.mediaDevices?.getUserMedia||!env.MediaRecorder)throw Error("Recording unsupported or HTTPS required");
  stopPlayback();releaseRecording();const ticket=++epoch;pending=true;
  try{const s=await env.navigator.mediaDevices.getUserMedia({audio:true});if(disposed||ticket!==epoch){s.getTracks().forEach(t=>t.stop());throw Error("Recording cancelled");}stream=s;const R=env.MediaRecorder;const mime=["audio/mp4","audio/webm;codecs=opus","audio/webm"].find(m=>R.isTypeSupported?.(m));const rec=new R(s,mime?{mimeType:mime}:undefined);recording=rec;const chunks=[];
   rec.ondataavailable=e=>{if(e.data.size)chunks.push(e.data);};rec.onerror=e=>{if(recording===rec){recording=null;stopTracks();status("error",e.error?.message||"recording");}};
   rec.onstop=()=>{if(recording!==rec)return;recording=null;stopTracks();if(disposed)return;const blob=new env.Blob(chunks,{type:rec.mimeType||chunks[0]?.type||""});if(!blob.size){status("error","empty-recording");return;}recordURL=env.URL.createObjectURL(blob);status("recorded",recordURL);};rec.start();status("recording",rec.mimeType);
  }catch(e){if(ticket===epoch){recording=null;stopTracks();status("error",e.message);}throw e;}finally{if(ticket===epoch)pending=false;}}
 function stopRecording(){if(pending){epoch++;pending=false;}if(recording&&recording.state!=="inactive")recording.stop();}
 function dispose(){disposed=true;stopPlayback();stopRecording();recording=null;stopTracks();releaseRecording();}
 return {play,stopPlayback,startRecording,stopRecording,releaseRecording,dispose,get recordingURL(){return recordURL;},voices:()=> (env.speechSynthesis?.getVoices()||[]).filter(v=>selectLocalTurkishVoice([v]))};
}
