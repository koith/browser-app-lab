/* Private TeraBox account viewer. Everything dynamic uses textContent / DOM nodes.
 * No raw post HTML, injected third-party embeds, tokens or persistence.
 */
(function(){
"use strict";
const $=id=>document.getElementById(id);
const accountSelect=$("accountSelect"),status=$("loadStatus"),results=$("results");
const detail=$("postDetail"),detailBody=$("detailBody");
const state={account:"",section:"posts",offset:0,more:false,loading:false,
             profile:null,records:[],accounts:[],viewVersion:0};
let detailRequestSeq=0;
const base=()=>"/api/account-archives/"+encodeURIComponent(state.account);
const sectionLabels={posts:"게시글·답글",followers:"팔로워",following:"팔로잉"};
function node(tag,className,text){
  const element=document.createElement(tag);
  if(className)element.className=className;
  if(text!==undefined && text!==null)element.textContent=String(text);
  return element;
}
function validLink(value){
  try{
    const parsed=new URL(value);
    return parsed.protocol==="https:"&&!parsed.username&&!parsed.password?parsed.href:"";
  }catch{return "";}
}
function anchor(url,label,cls){
  const href=validLink(url);
  if(!href)return node("span","muted",label);
  const a=node("a",cls||"",label);
  a.href=href;a.target="_blank";a.rel="noopener noreferrer";
  return a;
}
function fmt(value){
  if(!Number.isFinite(Number(value))||value===null||value==="")return "—";
  return Number(value).toLocaleString("ko-KR");
}
function date(value){
  const d=new Date(value);
  if(!Number.isFinite(d.getTime()))return "";
  return d.toLocaleString("ko-KR",{year:"numeric",month:"short",day:"numeric",
                                   hour:"2-digit",minute:"2-digit"});
}
async function get(path){
  const response=await fetch(path,{credentials:"same-origin",cache:"no-store",
                    headers:{Accept:"application/json"}});
  if(!response.ok)throw Error("보관본 조회 실패 (HTTP "+response.status+")");
  return response.json();
}
function showMessage(message){results.replaceChildren(node("p","placeholder",message));}
function setStatus(message){status.textContent=message;}
function resetProfile(){
  $("displayName").textContent="보관된 프로필을 불러오는 중…";
  $("handle").textContent="";$("biography").textContent="";
  $("postCount").textContent="—";$("followerCount").textContent="—";
  $("followingCount").textContent="—";$("profileFields").textContent="";
  $("cover").style.backgroundImage="";$("cover").classList.remove("has-image");
  $("avatar").style.backgroundImage="";$("avatar").textContent="?";
  $("profileStatus").textContent="프로필 보관본 확인 중";
  $("sourceProfile").hidden=true;
}
function renderProfile(profile){
  if(!profile.available){
    $("displayName").textContent="아직 프로필 보관본 없음";
    $("handle").textContent="";
    $("biography").textContent="백업 작업을 실행해 공개 프로필이 저장되면 표시됩니다.";
    $("profileStatus").textContent="UNVERIFIED · 프로필 백업 미확인";
    if(profile.profile_url){
      const a=$("sourceProfile");a.href=validLink(profile.profile_url)||"#";a.hidden=!validLink(profile.profile_url);
    }
    return;
  }
  state.profile=profile;
  $("displayName").textContent=profile.display_name||profile.handle||"공개 프로필";
  $("handle").textContent=profile.handle?("@"+profile.handle):"계정 ID "+(profile.identity||"");
  $("biography").textContent=profile.description||"공개 자기소개가 저장되지 않았습니다.";
  $("postCount").textContent=fmt(profile.posts_count);
  $("followerCount").textContent=fmt(profile.followers_count);
  $("followingCount").textContent=fmt(profile.following_count);
  const fields=profile.fields;
  $("profileFields").textContent=Array.isArray(fields)?
    fields.slice(0,12).map(f=>(f.name||"")+": "+(f.value||"").replace(/<[^>]*>/g,"")).join("\n"):"";
  const external=validLink(profile.profile_url),a=$("sourceProfile");
  a.hidden=!external;
  if(external)a.href=external;
  const avatar=profile.assets&&profile.assets.avatar;
  const banner=profile.assets&&profile.assets.banner;
  if(avatar){
    $("avatar").style.backgroundImage='url("'+avatar+'")';
    $("avatar").textContent="";
  }else $("avatar").textContent=($("displayName").textContent||"?").charAt(0).toUpperCase();
  if(banner){
    $("cover").style.backgroundImage='url("'+banner+'")';
    $("cover").classList.add("has-image");
  }
  const assets=[avatar?"프로필 원본 SHA 검증됨":"프로필 사진 미보관",
                banner?"헤더 원본 SHA 검증됨":"헤더 사진 미보관"];
  $("profileStatus").textContent="PROFILE SNAPSHOT · "+date(profile.captured_at)+
     " · "+assets.join(" · ")+" · 관계 목록/게시글 완전성 별도 확인 필요";
}
function mediaElement(item){
  const mime=String(item.mime||"");
  const url=item.url;
  if(!url||!item.verified_sha256)return node("div","media-unavailable","원본 파일 검증 대기");
  if(mime.startsWith("image/")){
    const img=node("img");
    img.src=url;img.loading="lazy";img.decoding="async";
    img.alt="SHA-256 검증된 보관 원본 이미지";
    img.addEventListener("click",()=>window.open(url,"_blank","noopener,noreferrer"));
    return img;
  }
  if(mime.startsWith("video/")){
    const video=node("video");
    video.controls=true;video.preload="metadata";video.playsInline=true;video.src=url;
    return video;
  }
  if(mime.startsWith("audio/")){
    const audio=node("audio");
    audio.controls=true;audio.preload="none";audio.src=url;
    return audio;
  }
  return node("div","media-unavailable","지원하지 않는 원본 미디어 형식");
}
function postCard(post,inDetail=false){
  const card=node("article","post");
  const head=node("header","post-head");
  const icon=node("span","post-avatar",
                  (state.profile?.display_name||state.profile?.handle||"A").charAt(0));
  head.append(icon);
  const metadata=node("div","post-meta");
  metadata.append(node("strong","",state.profile?.display_name||state.profile?.handle||"보관 계정"));
  const timestamp=node("time","",date(post.posted_at));metadata.append(timestamp);
  head.append(metadata,node("span","post-type",post.kind==="reply"?"답글":"게시글"));
  card.append(head,node("p","post-body",post.text||"(텍스트 없음)"));
  if(post.media&&post.media.length){
    const grid=node("div","post-media");
    for(const item of post.media)grid.append(mediaElement(item));
    card.append(grid);
  }
  const bottom=node("div","post-bottom");
  if(!inDetail){
    const btn=node("button","", "댓글·상세 보기");
    btn.type="button";btn.addEventListener("click",()=>openDetail(post));
    bottom.append(btn);
  }
  if(post.source_url)bottom.append(anchor(post.source_url,"SNS 원문",""));
  bottom.append(node("span","media-state",
    post.archive_complete?"첨부 "+fmt(post.media_saved)+"/"+fmt(post.media_expected)+"개 검증":
      "첨부 "+fmt(post.media_saved)+"/"+fmt(post.media_expected)+"개 · 일부 미보관"));
  card.append(bottom);
  return card;
}
function personCard(person){
  const row=node("article","person");
  row.append(node("div","person-icon",
         (person.display_name||person.handle||"?").charAt(0).toUpperCase()));
  const inner=node("div","person-main");
  inner.append(node("strong","",person.display_name||person.handle||"공개 계정"),
               node("small","",person.handle?"@"+person.handle:String(person.id||"")));
  row.append(inner);
  if(person.profile_url)row.append(anchor(person.profile_url,"프로필",""));
  return row;
}
function commentCard(item){
  const itemNode=node("section","comment");
  const header=node("header");
  header.append(node("b","",item.display_name||item.author||"공개 댓글"));
  if(item.author&&item.display_name&&item.author!==item.display_name)
    header.append(node("span","muted","@"+item.author));
  header.append(node("time","",date(item.posted_at)));
  itemNode.append(header,node("p","",item.text||"(텍스트 없음)"));
  if(item.source_url)itemNode.append(anchor(item.source_url,"댓글 원문"));
  if(item.media_source_links?.length){
    const text=node("p","muted","댓글 첨부는 현재 원본 링크만 확인됨 (테라박스 검증본 아님). ");
    itemNode.append(text);
    for(const link of item.media_source_links.slice(0,8))
      itemNode.append(anchor(link,"원본 첨부 링크"));
  }
  return itemNode;
}
async function openDetail(post){
  const requestSeq=++detailRequestSeq,selectedAccount=state.account;
  detailBody.replaceChildren(postCard(post,true),node("p","notice","공개 대화 기록 불러오는 중…"));
  detail.showModal();
  try{
    const thread=await get(base()+"/threads/"+post.id);
    if(!detail.open||requestSeq!==detailRequestSeq||state.account!==selectedAccount)return;
    const container=node("div");
    container.append(postCard(post,true));
    if(!thread.captured){
      container.append(node("p","notice","공개 댓글이 아직 백업되지 않았습니다. SNS 원문에서 추가 확인할 수 있습니다."));
    }else{
      container.append(node("p","notice",
        "공개 댓글 "+fmt(thread.replies.length)+"건 · 보관 시각 "+date(thread.captured_at)+
        (thread.truncated?" · 제공자 조회 수량 제한으로 일부만 확인":"")+
        " · 타인 댓글의 첨부 미디어는 링크만 표시될 수 있습니다."));
      for(const reply of thread.replies)container.append(commentCard(reply));
      if(!thread.replies.length)
        container.append(node("p","placeholder","보관된 공개 댓글이 없습니다."));
    }
    detailBody.replaceChildren(container);
  }catch{
    if(detail.open&&requestSeq===detailRequestSeq&&state.account===selectedAccount)
      detailBody.append(node("p","notice","댓글 보관본을 읽지 못했습니다. 저장 완료로 간주하지 않습니다."));
  }
}
function setTab(section){
  // A response for the previous tab must not block or overwrite this tab.
  state.viewVersion+=1;state.loading=false;
  state.section=section;state.offset=0;state.more=false;
  for(const btn of document.querySelectorAll("[data-section]")){
    const active=btn.dataset.section===section;
    if(btn.getAttribute("role")==="tab"){
      btn.classList.toggle("active",active);btn.setAttribute("aria-selected",String(active));
    }
  }
  $("more").hidden=true;$("more").disabled=false;
  showMessage("보관된 "+sectionLabels[section]+" 불러오는 중…");
  if(state.account)void nextPage();
}
async function nextPage(){
  if(state.loading||!state.account)return;
  state.loading=true;$("more").disabled=true;
  const selected=state.section,selectedAccount=state.account,offset=state.offset,
        requestVersion=state.viewVersion;
  try{
    const endpoint=selected==="posts"
       ?base()+"/feed?offset="+offset+"&limit=20"
       :base()+"/graph/"+selected+"?offset="+offset+"&limit=50";
    const data=await get(endpoint);
    if(state.account!==selectedAccount||state.section!==selected||
       state.viewVersion!==requestVersion)return;
    const records=selected==="posts"?data.posts:data.accounts;
    if(!Array.isArray(records))throw Error("보관본 페이지 형식이 올바르지 않습니다.");
    if(offset===0)results.replaceChildren();
    for(const item of records)results.append(selected==="posts"?postCard(item):personCard(item));
    if(!records.length&&offset===0)
      showMessage(selected==="posts"?"보관된 게시글이 없습니다. 백업 실행·완료 여부를 확인하세요.":"조회 가능한 공개 "+sectionLabels[selected]+" 목록이 없습니다.");
    state.offset+=records.length;
    // An empty page cannot advance an offset-based cursor; stop repeat loops.
    state.more=Boolean(data.more)&&records.length>0;
    $("more").hidden=!state.more;$("more").textContent="더 보기";
    setStatus(selected==="posts"?"게시글 "+fmt(data.total)+"건 중 "+fmt(state.offset)+"건 표시":
       "공개 관계 계정 "+fmt(data.captured_unique)+"명 보관 · "+fmt(state.offset)+"명 표시 (전체 명단 보장 안 됨)");
  }catch(error){
    if(state.account===selectedAccount&&state.section===selected&&
       state.viewVersion===requestVersion){
      const message=String(error.message||"보관 자료 불러오기 실패");
      // Preserve already verified cards; retry exactly the failed offset.
      if(offset===0)showMessage(message);
      else setStatus("추가 페이지 조회 실패 · 기존 보관본은 그대로 표시합니다. "+message);
      state.more=true;$("more").hidden=false;$("more").textContent="다시 시도";
    }
  }finally{
    if(state.viewVersion===requestVersion){state.loading=false;$("more").disabled=false;}
  }
}
async function selectAccount(value){
  // Cancel stale page and comment renders before changing account.
  state.viewVersion+=1;state.loading=false;
  $("more").hidden=true;$("more").disabled=false;
  detailRequestSeq+=1;
  if(detail.open)detail.close();
  state.account=value||"";state.profile=null;state.offset=0;state.section="posts";
  if(!value){
    resetProfile();$("displayName").textContent="계정을 선택하세요";
    showMessage("계정을 선택하세요.");setStatus("보관할 계정을 선택하세요.");
    return;
  }
  resetProfile();showMessage("게시글 보관본을 불러오는 중…");
  // The remote profile snapshot can take tens of seconds to verify. Start
  // post loading NOW, independently. A stale profile response must never
  // overwrite a newly selected account.
  setTab("posts");
  try{
    const profile=await get(base()+"/profile");
    if(state.account!==value)return;
    renderProfile(profile);
  }catch{
    if(state.account===value){
      $("displayName").textContent="프로필 저장 상태 미확인";
      $("profileStatus").textContent="프로필 원격 읽기 실패 · 보관 완료로 간주하지 않음";
    }
  }
}
async function init(){
  try{
    const data=await get("/api/account-archives");
    state.accounts=Array.isArray(data.accounts)?data.accounts:[];
    accountSelect.replaceChildren(node("option","",state.accounts.length?
                                          "계정을 선택하세요":"아직 등록된 계정 없음"));
    accountSelect.firstChild.value="";
    for(const item of state.accounts){
      const opt=node("option","",(item.platform==="bluesky"?"Bluesky":"Mastodon")+" · "+(item.profile_url||item.key));
      opt.value=item.key;accountSelect.append(opt);
    }
    const selected=new URL(location.href).searchParams.get("account");
    const first=state.accounts.find(a=>a.key===selected)||state.accounts[0];
    if(first){accountSelect.value=first.key;await selectAccount(first.key);}
    else{setStatus("등록된 비공개 계정 아카이브가 없습니다.");showMessage("계정 분석에서 공개 계정을 지정해 백업을 시작하세요.");}
  }catch(error){
    setStatus("비공개 보관함을 불러오지 못했습니다.");
    showMessage("개인용 아카이브 서버 인증 또는 저장 연결 상태를 확인하세요.");
  }
}
accountSelect.addEventListener("change",()=>void selectAccount(accountSelect.value));
document.querySelectorAll("[data-section]").forEach(btn=>btn.addEventListener(
  "click",()=>setTab(btn.dataset.section)));
$("more").addEventListener("click",()=>void nextPage());
$("closeDetail").addEventListener("click",()=>detail.close());
detail.addEventListener("click",event=>{if(event.target===detail)detail.close();});
detail.addEventListener("close",()=>{detailRequestSeq+=1;detailBody.replaceChildren();});
void init();
})();
