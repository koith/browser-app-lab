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
const ACCOUNT_KEY=/^(?:bluesky|mastodon)-[a-f0-9]{40}$/;
const params=new URLSearchParams(location.search);
const embedded=params.get("embedded")==="1";
if(embedded)document.body.classList.add("archive-embedded");
function setPlatformTheme(accountKey){
  const provider=String(accountKey||"").startsWith("mastodon-")?"mastodon":"bluesky";
  document.documentElement.dataset.platform=provider;
  $("snsProviderSymbol").textContent=provider==="mastodon"?"M":"🦋";
  $("snsProviderTitle").textContent=provider==="mastodon"?"Mastodon 스타일 보관함":"Bluesky 스타일 보관함";
  $("snsProviderSubtitle").textContent=provider==="mastodon"
    ?"Mastodon 공개 계정 보관본 · 실시간 타임라인 아님"
    :"Bluesky 공개 계정 보관본 · 실시간 피드 아님";
  $("detailTitle").textContent=provider==="mastodon"?"보관된 게시물 · 대화":"게시글 · 대화";
}
function accountLabel(item){
  const name=typeof item?.display_name==="string"?item.display_name.trim().replace(/\s+/g," ").slice(0,100):"";
  const handle=typeof item?.handle==="string"?item.handle.trim().replace(/^@+/,"").slice(0,200):"";
  if(name&&handle)return name+"(@"+handle+")";
  if(name)return name+"(아이디 미보관)";
  if(handle)return "닉네임 미보관(@"+handle+")";
  return "이름 미보관 ("+(item?.platform==="mastodon"?"Mastodon":"Bluesky")+" 계정)";
}
function setAccountUrl(value){
  if(!ACCOUNT_KEY.test(value))return;
  if(params.get("account")!==value){
    params.set("account",value);
    history.replaceState(null,"",location.pathname+"?"+params.toString());
  }
  if(window.parent!==window)window.parent.postMessage(
    {type:"intersection:archive-selected",account:value},location.origin);
}
function setAccountOption(item){
  const opt=[...accountSelect.options].find(o=>o.value===item.key);
  if(opt)opt.textContent=accountLabel(item);
}
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
function syncVisiblePostIdentity(){
  // The feed loads independently of remote profile verification. When posts
  // arrive first, update their bylines after the saved profile arrives rather
  // than leaving a generic author on an otherwise faithful SNS-style feed.
  const name=state.profile?.display_name||state.profile?.handle||"보관 계정";
  const handle=state.profile?.handle?"@"+state.profile.handle:"";
  const avatar=state.profile?.assets?.avatar||"";
  for(const card of document.querySelectorAll("#results .post,#detailBody .post")){
    const heading=card.querySelector(".post-byline strong");
    if(heading)heading.textContent=name;
    const byline=card.querySelector(".post-byline");
    let handleNode=byline?.querySelector(".post-handle");
    if(handle&&!handleNode&&byline){
      handleNode=node("span","post-handle");byline.append(handleNode);
    }
    if(handleNode)handleNode.textContent=handle;
    const icon=card.querySelector(".post-avatar");
    if(icon&&typeof avatar==="string"&&avatar.startsWith("/api/account-archives/")){
      icon.style.backgroundImage='url("'+avatar+'")';icon.textContent="";
    }else if(icon){
      icon.style.backgroundImage="";
      icon.textContent=name.charAt(0).toUpperCase();
    }
  }
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
  const current=state.accounts.find(item=>item.key===state.account);
  if(current){
    if(profile.display_name)current.display_name=profile.display_name;
    if(profile.handle)current.handle=profile.handle;
    setAccountOption(current);
  }
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
  syncVisiblePostIdentity();
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
  card.dataset.kind=post.revision_of?"revision":post.kind==="reply"?"reply":"post";
  const head=node("header","post-head");
  const icon=node("span","post-avatar",
                  (state.profile?.display_name||state.profile?.handle||"A").charAt(0));
  const savedAvatar=state.profile?.assets?.avatar||"";
  if(typeof savedAvatar==="string"&&savedAvatar.startsWith("/api/account-archives/")){
    icon.style.backgroundImage='url("'+savedAvatar+'")';icon.textContent="";
  }
  head.append(icon);
  const metadata=node("div","post-meta"),byline=node("div","post-byline");
  byline.append(node("strong","",state.profile?.display_name||state.profile?.handle||"보관 계정"));
  if(state.profile?.handle)byline.append(node("span","post-handle","@"+state.profile.handle));
  metadata.append(byline,node("time","post-date",date(post.posted_at)));
  head.append(metadata,node("span","post-type",
    post.revision_of?"수정 이력":post.kind==="reply"?"↳ 답글":"보관 게시글"));
  card.append(head,node("p","post-body",post.text||"(텍스트 없음)"));
  if(post.revision_of){
    card.append(node("p","notice","이전 원문은 그대로 보관 · 변경본 추가 저장 "+
      (date(post.captured_at)||"")));
  }
  if(post.media&&post.media.length){
    const grid=node("div","post-media");
    grid.dataset.count=String(post.media.length);
    for(const item of post.media)grid.append(mediaElement(item));
    card.append(grid);
  }
  const bottom=node("div","post-bottom");
  if(!inDetail){
    const btn=node("button","post-action post-action-reply","댓글·상세 보기");
    btn.type="button";btn.setAttribute("aria-label","댓글·상세 보기");
    btn.addEventListener("click",()=>openDetail(post));
    bottom.append(btn);
  }
  if(post.source_url){
    const sourceLink=anchor(post.source_url,"SNS 원문 ↗","post-action post-action-source");
    sourceLink.setAttribute("aria-label","SNS 원문");
    bottom.append(sourceLink);
  }
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
  const commentIcon=node("span","comment-avatar",(item.display_name||item.author||"?").charAt(0).toUpperCase());
  const content=node("div","comment-content");
  const header=node("header");
  header.append(node("b","",item.display_name||item.author||"공개 댓글"));
  if(item.author&&item.display_name&&item.author!==item.display_name)
    header.append(node("span","muted","@"+item.author));
  header.append(node("time","",date(item.posted_at)));
  content.append(header,node("p","",item.text||"(텍스트 없음)"));
  if(item.source_url)content.append(anchor(item.source_url,"댓글 원문 ↗","comment-source"));
  if(item.media_source_links?.length){
    const text=node("p","muted","댓글 첨부는 원본 링크만 확인됨 · 검증 보관 파일이 아닙니다.");
    content.append(text);
    for(const link of item.media_source_links.slice(0,8))
      content.append(anchor(link,"첨부 원본 링크 ↗","comment-source"));
  }
  itemNode.append(commentIcon,content);
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
  setPlatformTheme(state.account);
  if(value)setAccountUrl(value);
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
  // The parent preloads labels once, and passes the selected verified key.
  // Embedded views must not download and decrypt the same large ZIP again.
  const selected=params.get("account")||"";
  if(embedded){
    if(ACCOUNT_KEY.test(selected)){
      accountSelect.replaceChildren(node("option","","선택한 계정"));
      accountSelect.firstChild.value=selected;
      accountSelect.value=selected;
      await selectAccount(selected);
    }else{
      setStatus("상단에서 보관된 계정을 선택하세요.");
      showMessage("계정 목록을 불러오는 중…");
    }
    return;
  }
  try{
    const data=await get("/api/account-archives");
    state.accounts=Array.isArray(data.accounts)?data.accounts.filter(
      item=>ACCOUNT_KEY.test(item.key)):[];
    state.accounts.sort((a,b)=>accountLabel(a).localeCompare(accountLabel(b),"ko-KR"));
    const count=$("accountCount");
    if(count)count.textContent="보관된 계정 "+state.accounts.length+"개";
    accountSelect.replaceChildren();
    if(!state.accounts.length){
      const opt=node("option","","아직 보관된 계정 없음");opt.value="";
      accountSelect.append(opt);
      setStatus("등록된 계정 보관본이 없습니다.");
      showMessage("계정 분석에서 공개 계정을 지정해 백업을 시작하세요.");
      return;
    }
    for(const item of state.accounts){
      const opt=node("option","",accountLabel(item));
      opt.value=item.key;accountSelect.append(opt);
    }
    const first=state.accounts.find(a=>a.key===selected)||state.accounts[0];
    accountSelect.value=first.key;
    setStatus("보관된 계정 "+state.accounts.length+"개 · 자동으로 최신 보관본을 표시합니다.");
    await selectAccount(first.key);
  }catch(error){
    const count=$("accountCount");
    if(count)count.textContent="불러오기 실패";
    setStatus("계정 목록 연결에 실패했습니다. 다시 열면 자동 재시도합니다.");
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
