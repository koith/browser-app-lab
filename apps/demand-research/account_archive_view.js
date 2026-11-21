/* Private TeraBox account viewer. Everything dynamic uses textContent / DOM nodes.
 * No raw post HTML, injected third-party embeds, tokens or persistence.
 */
(function(){
"use strict";
const $=id=>document.getElementById(id);
const accountSelect=$("accountSelect"),status=$("loadStatus"),results=$("results");
const detail=$("postDetail"),detailBody=$("detailBody");
const state={account:"",section:"posts",offset:0,more:false,loading:false,
             profile:null,records:[],accounts:[],viewVersion:0,
             firstPageRetries:0,retryTimer:null};
let detailRequestSeq=0;
const base=()=>"/api/account-archives/"+encodeURIComponent(state.account);
const sectionLabels={posts:"게시글",replies:"답글",activity:"활동",media:"미디어",videos:"동영상",featured:"고정됨",followers:"팔로워",following:"팔로잉"};
const journalSection=section=>["posts","replies","activity","media","videos","featured"].includes(section);
const ACCOUNT_KEY=/^(?:bluesky|mastodon)-[a-f0-9]{40}$/;
const params=new URLSearchParams(location.search);
const embedded=params.get("embedded")==="1";
const feedSearch=$("feedSearch"),feedQuery=$("feedQuery"),
      feedKind=$("feedKind"),feedMediaStatus=$("feedMediaStatus");
if(embedded)document.body.classList.add("archive-embedded");
if(typeof params.get("q")==="string")feedQuery.value=params.get("q").slice(0,100);
if(["","post","reply","revision"].includes(params.get("kind")||""))
  feedKind.value=params.get("kind")||"";
if(["","complete","partial"].includes(params.get("media_status")||""))
  feedMediaStatus.value=params.get("media_status")||"";
let feedSearchTimer=null;
// Previously rendered, SHA-backed SAME-account DOM only. No persistent cache.
let savedPostsView=null;
const POSTS_VIEW_MAX_AGE_MS=90_000;
function feedFilterKey(){
  return JSON.stringify([feedQuery.value.trim().slice(0,100),
    feedKind.value,feedMediaStatus.value]);
}
function invalidateSavedPostsView(){savedPostsView=null;}

function persistFeedFilters(){
  for(const [key,value] of [
    ["q",feedQuery.value.trim().slice(0,100)],
    ["kind",feedKind.value],["media_status",feedMediaStatus.value]]){
    if(value)params.set(key,value);else params.delete(key);
  }
  history.replaceState(null,"",location.pathname+"?"+params.toString());
}
function resetFeedSearch(){
  invalidateSavedPostsView();
  if(feedSearchTimer!==null){clearTimeout(feedSearchTimer);feedSearchTimer=null;}
  persistFeedFilters();
  if(journalSection(state.section))setTab(state.section);
}
function scheduleFeedSearch(){
  invalidateSavedPostsView();
  if(feedSearchTimer!==null)clearTimeout(feedSearchTimer);
  // Invalidate pending old results as soon as text changes.
  state.viewVersion++;state.loading=false;state.offset=0;state.more=false;
  $("more").hidden=true;showMessage("보관된 모든 글에서 검색 중…");
  feedSearchTimer=setTimeout(()=>{feedSearchTimer=null;resetFeedSearch();},300);
}
function renderAccountChoices(){
  const term=($("accountSearch")?.value||"").trim().toLocaleLowerCase("ko-KR");
  const filtered=state.accounts.filter(item=>
    !term||accountLabel(item).toLocaleLowerCase("ko-KR").includes(term));
  accountSelect.replaceChildren();
  if(!filtered.length){
    const empty=node("option","","일치하는 계정 없음");
    empty.value="";accountSelect.append(empty);
  }else for(const item of filtered){
    const opt=node("option","",accountLabel(item));
    opt.value=item.key;accountSelect.append(opt);
  }
  accountSelect.disabled=!filtered.length;
  if(filtered.some(item=>item.key===state.account))
    accountSelect.value=state.account;
  else if(filtered.length)
    accountSelect.selectedIndex=0;
  if($("accountCount"))$("accountCount").textContent=
    "보관 계정 "+filtered.length+"/"+state.accounts.length+"개";
}
function setPlatformTheme(accountKey){
  const provider=String(accountKey||"").startsWith("mastodon-")?"mastodon":"bluesky";
  const mastodon=provider==="mastodon";
  for(const btn of document.querySelectorAll(".tabs [data-section]")){
    const section=btn.dataset.section;
    btn.hidden=mastodon?!(["activity","media","featured"].includes(section)):
                        !(["posts","replies","media","videos"].includes(section));
  }
  $("mastodonActivityControls").hidden=!mastodon;
  document.documentElement.dataset.platform=provider;
  $("snsProviderSymbol").textContent=provider==="mastodon"?"M":"🦋";
  $("snsProviderTitle").textContent=provider==="mastodon"?"Mastodon":"Bluesky";
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
async function loadVerifiedProfileWithRetry(account){
  // The signed ZIP mirror can briefly return 502/503 while its verified
  // source is restored. A failed request is never evidence of a missing backup.
  const delays=[0,1600,3900,7700,15000];
  for(let attempt=0;attempt<delays.length;attempt++){
    if(state.account!==account)return null;
    if(delays[attempt]){
      await new Promise(resolve=>window.setTimeout(resolve,delays[attempt]));
      if(state.account!==account)return null;
    }
    try{return await get(base()+"/profile");}
    catch(error){
      if(!/(?:HTTP (?:502|503|504)|failed to fetch|networkerror)/i.test(
         String(error?.message||""))||attempt===delays.length-1)throw error;
      $("profileStatus").textContent="원본 프로필 검증 서버 일시 지연 · 자동 복구 "+(attempt+1)+"/4";
    }
  }
  return null;
}
function showMessage(message){results.replaceChildren(node("p","placeholder",message));}
function setStatus(message){status.textContent=message;}
function resetProfile(){
  $("displayName").textContent="프로필 확인 중…";
  $("handle").textContent="";$("biography").textContent="";
  $("postCount").textContent="—";$("followerCount").textContent="—";
  $("followingCount").textContent="—";$("profileFields").textContent="";
  // Release any prior account's image before displaying another account.
  for(const kind of ["avatar","banner"]){
    const image=$(kind==="banner"?"coverImage":"avatarImage");
    image.onload=null;image.onerror=null;image.hidden=true;image.removeAttribute("src");
  }
  $("cover").classList.remove("has-image");
  $("avatar").classList.remove("has-image");
  $("avatarFallback").hidden=false;$("avatarFallback").textContent="?";
  $("profileStatus").textContent="보관된 원본의 프로필 정보를 확인하는 중입니다.";
  $("sourceProfile").hidden=true;
  $("profileExtras").hidden=true;
  $("profileExtras").replaceChildren();
  $("profileHistory").hidden=true;
  $("profileHistoryList").replaceChildren();
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
function renderExtraProfileFields(profile){
  const area=$("profileExtras");
  area.replaceChildren();
  const addText=(label,value)=>{
    if(typeof value!=="string"||!value.trim())return;
    const row=node("span","profile-extra");
    row.append(node("strong","",label+" "),node("span","",value.trim().slice(0,1000)));
    area.append(row);
  };
  if(profile.platform==="bluesky"){
    addText("호칭",profile.pronouns);
    const pinned=profile.pinned_post?.uri;
    if(typeof pinned==="string"&&pinned.startsWith("at://"+profile.identity+"/app.bsky.feed.post/")){
      const rkey=pinned.split("/").pop();
      const src=validLink(profile.profile_url);
      if(src&&/^[A-Za-z0-9._~-]{1,100}$/.test(rkey||"")){
        const row=node("span","profile-extra");
        row.append(anchor(src.replace(/\/$/,"")+"/post/"+rkey,"고정 게시물 원문","profile-link"));
        area.append(row);
      }
    }
  }
  if(profile.platform==="mastodon"){
    if(profile.bot===true)addText("계정 유형","자동화 계정");
    if(profile.locked===true)addText("팔로우 상태","승인 필요");
    // Source Mastodon displays alt text to assistive technology, not as
    // extra visible profile rows that shift every subsequent screenshot.
    const cover=$("cover"),avatar=$("avatar");
    cover.setAttribute("role","img");
    cover.setAttribute("aria-label",profile.header_description||
      "보관된 공개 프로필 헤더 배경");
    avatar.setAttribute("aria-label",profile.avatar_description||
      "보관된 공개 프로필 사진");
  }
  const site=validLink(profile.website);
  if(site){
    const row=node("span","profile-extra");
    row.append(anchor(site,"공개 웹사이트","profile-link"));
    area.append(row);
  }
  if(typeof profile.created_at==="string"&&profile.created_at)
    addText("가입 기록",date(profile.created_at));
  area.hidden=!area.childNodes.length;
}
function renderProfileHistory(profile){
  const details=$("profileHistory"),list=$("profileHistoryList");
  list.replaceChildren();
  const versions=Array.isArray(profile.history)?profile.history:[];
  details.hidden=versions.length<2;
  if(details.hidden)return;
  const selectedAccount=state.account;
  for(const version of versions){
    if(!version||typeof version.id!=="string"||
       !/^snap-[0-9]{20}-[a-f0-9]{16}\.json$/.test(version.id))continue;
    const active=version.id===profile.snapshot_id;
    const button=node("button","profile-version"+(active?" active":""),date(version.captured_at)||"보관 시각 미상");
    button.type="button";button.disabled=active;
    button.setAttribute("aria-current",active?"true":"false");
    const badges=[];
    if(version.assets?.banner==="sha256_verified")badges.push("헤더 이미지");
    if(version.assets?.avatar==="sha256_verified")badges.push("프로필 사진");
    if(version.has_description)badges.push("자기소개");
    button.append(node("small","",badges.length?badges.join(" · "):"텍스트·이미지 일부 미보관"));
    button.addEventListener("click",async()=>{
      if(state.account!==selectedAccount)return;
      button.disabled=true;
      $("profileStatus").textContent="선택한 이전 프로필 기록의 원본을 확인하고 있습니다.";
      try{
        const previous=await get(base()+"/profile?snapshot="+encodeURIComponent(version.id));
        if(state.account!==selectedAccount)return;
        renderProfile(previous);
      }catch{
        if(state.account===selectedAccount)
          $("profileStatus").textContent="이전 프로필 기록을 확인하지 못했습니다. 원본은 변경하지 않았습니다.";
      }finally{button.disabled=false;}
    });
    list.append(button);
  }
}

function validArchivedProfileImage(path,kind){
  // The deployed snapshot API uses ?snapshot=<verified archive snapshot id>.
  // Accept only this account's archive image, never an external URL or
  // another account's media. Versioned links are essential for history.
  if(typeof path!=="string"||path.length>420||!ACCOUNT_KEY.test(state.account))return "";
  const prefix="/api/account-archives/"+state.account+"/profile-asset/"+kind;
  if(path===prefix)return path;
  if(!path.startsWith(prefix))return "";
  const suffix=path.slice(prefix.length);
  return /^\?snapshot=snap-[0-9]{20}-[a-f0-9]{16}\.json$/.test(suffix)?path:"";
}
function applyArchivedProfileImage(kind,path){
  // Actual <img> decoding avoids silently hiding 404/502 behind CSS.
  const frame=$(kind==="banner"?"cover":"avatar");
  const image=$(kind==="banner"?"coverImage":"avatarImage");
  const fallback=$("avatarFallback");
  const account=state.account;
  const selected=state.profile;
  const valid=validArchivedProfileImage(path,kind);
  image.onload=null;image.onerror=null;
  image.hidden=true;image.removeAttribute("src");
  frame.classList.remove("has-image");
  if(kind==="avatar")fallback.hidden=false;
  if(!valid)return;
  image.onload=()=>{
    if(state.account!==account||state.profile!==selected||image.getAttribute("src")!==valid)return;
    if(!image.naturalWidth||!image.naturalHeight){image.onerror();return;}
    image.hidden=false;frame.classList.add("has-image");
    if(kind==="avatar")fallback.hidden=true;
  };
  image.onerror=()=>{
    if(state.account!==account||state.profile!==selected||image.getAttribute("src")!==valid)return;
    image.hidden=true;frame.classList.remove("has-image");
    if(kind==="avatar")fallback.hidden=false;
    const msg=kind==="banner"?"헤더 이미지 파일을 읽지 못했습니다.":"프로필 사진 파일을 읽지 못했습니다.";
    const status=$("profileStatus");
    if(!status.textContent.includes(msg))status.textContent+=" · "+msg;
  };
  image.src=valid;
}
function renderProfile(profile){
  if(!profile.available){
    $("displayName").textContent="아직 프로필 보관본 없음";
    $("handle").textContent="";
    $("biography").textContent="백업 작업을 실행해 공개 프로필이 저장되면 표시됩니다.";
    $("profileStatus").textContent="UNVERIFIED · 프로필 백업 미확인";
    $("profileHistory").hidden=true;$("profileExtras").hidden=true;
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
  $("snsProviderTitle").textContent=profile.display_name||profile.handle||
    (state.account.startsWith("mastodon-")?"Mastodon":"Bluesky");
  $("handle").textContent=profile.handle?("@"+profile.handle):"계정 ID "+(profile.identity||"");
  $("biography").textContent=typeof profile.description==="string"&&profile.description.trim()
    ?profile.description:"수집된 프로필에 등록된 자기소개가 없습니다.";
  $("postCount").textContent=fmt(profile.posts_count);
  if(profile.platform==="mastodon"){
    const featured=document.querySelector('.tabs [data-section="featured"]');
    const mediaTab=document.querySelector('.tabs [data-section="media"]');
    if(featured)featured.hidden=profile.show_featured===false;
    if(mediaTab)mediaTab.hidden=profile.show_media===false;
    if((state.section==="media"&&profile.show_media===false)||
       (state.section==="featured"&&profile.show_featured===false))
      setTab("activity");
  }
  $("followerCount").textContent=fmt(profile.followers_count);
  $("followingCount").textContent=fmt(profile.following_count);
  // Do not flatten Mastodon 4.6 profile fields into an artificial
  // colon-separated paragraph. Render every archived public field in
  // source order and preserve only independently sanitized HTTPS links.
  const fields=Array.isArray(profile.fields_rendered)?
    profile.fields_rendered:(Array.isArray(profile.fields)?profile.fields:[]);
  const fieldsHost=$("profileFields");
  fieldsHost.replaceChildren();
  for(const field of fields){
    if(!field||typeof field!=="object")continue;
    const row=node("dl","profile-field");
    row.append(node("dt","profile-field-name",field.name||""));
    const value=node("dd","profile-field-value");
    if(Array.isArray(field.parts)){
      for(const part of field.parts){
        if(!part||typeof part.text!=="string")continue;
        const safe=validLink(part.href||"");
        if(safe)value.append(anchor(safe,part.text,"profile-field-link"));
        else value.append(document.createTextNode(part.text));
      }
    }else if(typeof field.value==="string"){
      value.textContent=field.value.replace(/<[^>]*>/g," ");
    }
    row.append(value);
    if(typeof field.verified_at==="string"&&field.verified_at)
      row.append(node("span","profile-field-verified","✓ 확인된 링크"));
    fieldsHost.append(row);
  }
  fieldsHost.hidden=!fieldsHost.childElementCount;
  renderExtraProfileFields(profile);
  renderProfileHistory(profile);
  const external=validLink(profile.profile_url),a=$("sourceProfile");
  a.hidden=!external;
  if(external)a.href=external;
  const avatar=profile.assets&&profile.assets.avatar;
  const banner=profile.assets&&profile.assets.banner;
  $("avatarFallback").textContent=($("displayName").textContent||"?").charAt(0).toUpperCase();
  applyArchivedProfileImage("avatar",avatar);
  applyArchivedProfileImage("banner",banner);
  function assetEvidence(kind,present){
    const meta=profile.asset_status?.[kind]||{};
    const label=kind==="avatar"?"프로필 사진":"헤더 이미지";
    if(!present)return label+(meta.status==="not_set"?" 미설정":" 미보관");
    if(meta.historical_fallback)
      return label+" · 이전 저장본("+date(meta.captured_at)+")";
    if(meta.source_tier==="public_bluesky_cdn_rendition")
      return label+" · 공개 CDN 화질본 SHA 검증";
    if(meta.source_tier==="original_pds_blob")
      return label+" · PDS 원본 SHA 검증";
    return label+" · 저장본 SHA 검증";
  }
  const assets=[assetEvidence("avatar",avatar),assetEvidence("banner",banner)];
  $("profileStatus").textContent=(profile.latest_snapshot?"최신 프로필 보관본":"이전 프로필 보관본")+
    " · "+date(profile.captured_at)+" · "+assets.join(" · ")+
    " · 다른 시점 기록은 아래 이력에서 선택";
  syncVisiblePostIdentity();
}
function showVerifiedPickerPreview(item){
  // The parent already loaded the source-bound, AES/SHA verified archive
  // picker. Display its name/handle at once, without pretending that the
  // full profile, bio, avatar or source ZIP has finished loading.
  if(!item||item.key!==state.account||!ACCOUNT_KEY.test(item.key))return;
  const clean=s=>typeof s==="string"?s.replace(/[\r\n\u0000-\u001f]/g," ").trim():"";
  const name=clean(item.display_name).slice(0,100);
  const handle=clean(item.handle).replace(/^@+/,"").slice(0,200);
  if(!name&&!handle)return;
  if(!state.profile){
    $("displayName").textContent=name||handle;
    $("handle").textContent=handle?"@"+handle:"";
    $("snsProviderTitle").textContent=name||handle;
    $("profileStatus").textContent="계정 이름·아이디 표시됨 · 원본 프로필 및 게시글 확인 중";
  }
}
if(embedded){
  window.addEventListener("message",event=>{
    if(event.origin!==location.origin||event.source!==window.parent)return;
    const message=event.data;
    if(message?.type==="intersection:archive-preview")
      showVerifiedPickerPreview(message.item);
    if(message?.type==="intersection:archive-switch"&&
       ACCOUNT_KEY.test(message.account)&&message.account!==state.account)
      void selectAccount(message.account);
  });
}
function safeMediaPath(value){
  if(typeof value!=="string"||value.length>300)return "";
  try{
    const url=new URL(value,location.origin);
    return url.origin===location.origin&&!url.search&&!url.hash&&
      /^\/api\/account-archives\/(?:bluesky|mastodon)-[a-f0-9]{40}\/media\/[a-f0-9]{40}\/(?:[0-9]|1[0-5])$/.test(url.pathname)
        ?url.pathname:"";
  }catch{return "";}
}
function mediaElement(item,index,altText=""){
  const slot=node("div","media-slot");
  const mime=String(item?.mime||""),url=item?.verified_sha256===true?safeMediaPath(item.url):"";
  if(!url||!(/^(image|video|audio)\//).test(mime)){
    slot.classList.add("media-missing");
    slot.append(node("div","media-unavailable","첨부 "+(index+1)+" · 원본 미보관 또는 검증 불가"));
    return slot;
  }
  let el;
  if(mime.startsWith("image/")){
    el=node("img");
    el.src=url;el.loading="lazy";el.decoding="async";
    el.alt=altText||("원본 보관 이미지 · 첨부 "+(index+1));
    el.addEventListener("click",()=>window.open(url,"_blank","noopener,noreferrer"));
  }else if(mime.startsWith("video/")){
    el=node("video");el.controls=true;el.preload="metadata";el.playsInline=true;el.src=url;
  }else{
    el=node("audio");el.controls=true;el.preload="none";el.src=url;
  }
  el.addEventListener("error",()=>{
    if(!slot.isConnected)return;
    slot.replaceChildren(node("div","media-unavailable",
      "첨부 "+(index+1)+" · 보관 원본 표시 실패 (서버 재확인 필요)"));
    slot.classList.add("media-missing");
  });
  slot.append(el);
  return slot;
}
function richPostBody(post){
  const p=node("p","post-body");
  const parts=Array.isArray(post.rich_text)?post.rich_text:[];
  if(!parts.length){p.textContent=post.text||"(텍스트 없음)";return p;}
  for(const part of parts.slice(0,300)){
    if(!part||typeof part.text!=="string")continue;
    const content=part.text.slice(0,30000),href=validLink(part.href||"");
    if(href)p.append(anchor(href,content,"post-inline-link"));
    else p.append(document.createTextNode(content));
  }
  if(!p.textContent.trim())p.textContent=post.text||"(텍스트 없음)";
  return p;
}
function engagementBar(post,inDetail){
  const row=node("div","post-bottom");
  const stats=post.engagement||{};
  const actions=[
    ["reply","↩",stats.replies_count,"답글"],
    ["repost","⇄",stats.reblogs_count,"공유"],
    ["like","♡",stats.favourites_count,"좋아요"]];
  for(const [type,icon,count,label] of actions){
    const span=node("span","post-metric post-metric-"+type);
    span.setAttribute("aria-label",label+(Number.isInteger(count)?" "+fmt(count)+"개":" · 수치 미보관"));
    span.append(node("span","post-metric-icon",icon));
    if(Number.isInteger(count))span.append(node("span","",fmt(count)));
    row.append(span);
  }
  if(!inDetail){
    const btn=node("button","post-action post-action-reply","대화 보기");
    btn.type="button";btn.setAttribute("aria-label","댓글·상세 보기");
    btn.addEventListener("click",()=>openDetail(post));row.append(btn);
  }
  if(post.source_url){
    const original=anchor(post.source_url,"원문","post-action post-action-source");
    original.setAttribute("aria-label","SNS 원문");row.append(original);
  }
  return row;
}
function postCard(post,inDetail=false){
  const card=node("article","post");
  card.dataset.kind=post.revision_of?"revision":post.kind||"post";
  const head=node("header","post-head");
  const icon=node("span","post-avatar",
     (state.profile?.display_name||state.profile?.handle||"A").charAt(0));
  const avatar=state.profile?.assets?.avatar||"";
  if(typeof avatar==="string"&&avatar.startsWith("/api/account-archives/")){
    icon.style.backgroundImage='url("'+avatar+'")';icon.textContent="";
  }
  const metadata=node("div","post-meta"),byline=node("div","post-byline");
  byline.append(node("strong","",state.profile?.display_name||state.profile?.handle||"보관 계정"));
  if(state.profile?.handle)
    byline.append(node("span","post-handle","@"+state.profile.handle));
  metadata.append(byline,node("time","post-date",date(post.posted_at)));
  head.append(icon,metadata);
  const tag=post.revision_of?"수정 기록":post.kind==="reply"?"답글":
            post.kind==="reblog"?"리블로그":"";
  if(tag)head.append(node("span","post-type",tag));
  if(post.pinned || (state.profile?.pinned_post?.uri&&
      state.profile.pinned_post.uri===post.original_id))
    card.append(node("div","post-pinned","⌑ 고정된 게시물"));
  if(post.reblog){
    const share=node("div","post-reblog-note");
    share.append(node("span","","⇄ "+(post.reblog.name||post.reblog.handle||"원문 작성자")+"님의 글을 공유"));
    if(post.reblog.url)share.append(anchor(post.reblog.url," 작성자","post-inline-link"));
    card.append(share);
  }
  card.append(head);
  const content=node("div","post-content");
  if(post.content_warning){
    content.append(node("p","content-warning","⚠ "+post.content_warning));
  }
  const rich=richPostBody(post);
  const mediaAssets=node("div","post-attachments");
  if(post.revision_of)
    mediaAssets.append(node("p","notice","이전 보관본은 유지되며 수정 내용은 별도 기록됩니다."));
  const stored=Array.isArray(post.media)?post.media:[];
  const expected=Number.isSafeInteger(Number(post.media_expected))
    ?Math.max(0,Number(post.media_expected)):0;
  const byIndex=new Map();
  for(const item of stored){
    const i=item?.index;
    if(Number.isInteger(i)&&i>=0&&i<16&&!byIndex.has(i))byIndex.set(i,item);
  }
  const count=Math.min(16,Math.max(expected,stored.length,
    ...(byIndex.size?[...byIndex.keys()].map(i=>i+1):[0])));
  if(count){
    const grid=node("div","post-media");grid.dataset.count=String(count);
    for(let i=0;i<count;i++)
      grid.append(mediaElement(byIndex.get(i),i,
        Array.isArray(post.alt_text)?post.alt_text[i]||"":""));
    mediaAssets.append(grid);
  }
  if(post.external_card?.url){
    const external=node("div","post-external-card");
    external.append(anchor(post.external_card.url,
      post.external_card.title||"공개 링크","post-card-title"));
    if(post.external_card.description)
      external.append(node("p","post-card-summary",post.external_card.description));
    mediaAssets.append(external);
  }
  if(post.quoted_post?.url){
    const quoteBox=node("div","post-quote");
    quoteBox.append(node("span","post-quote-label","인용 게시물"));
    quoteBox.append(anchor(post.quoted_post.url,"원본 인용 게시물 보기","post-inline-link"));
    mediaAssets.append(quoteBox);
  }
  if(post.poll && Array.isArray(post.poll.options)){
    const poll=node("div","post-poll");
    poll.append(node("strong","", "보관된 투표"+(post.poll.expired?" · 종료":"")));
    for(const option of post.poll.options.slice(0,20)){
      const label=option.title+(Number.isInteger(option.votes_count)?
        " · "+fmt(option.votes_count)+"표":"");
      poll.append(node("div","post-poll-option",label));
    }
    mediaAssets.append(poll);
  }
  content.append(rich,mediaAssets);
  if(post.sensitive){
    content.classList.add("post-sensitive");
    const reveal=node("button","reveal-sensitive","콘텐츠 경고 · 내용 보기");
    reveal.type="button";
    reveal.setAttribute("aria-expanded","false");
    reveal.addEventListener("click",()=>{
      const shown=!content.classList.contains("revealed");
      content.classList.toggle("revealed",shown);
      reveal.textContent=shown?"내용 가리기":"콘텐츠 경고 · 내용 보기";
      reveal.setAttribute("aria-expanded",String(shown));
    });
    card.append(reveal);
  }
  card.append(content,engagementBar(post,inDetail));
  const meta=node("div","archive-meta");
  meta.append(node("span","media-state",post.archive_complete?
    "원본 첨부 "+fmt(post.media_saved)+"/"+fmt(post.media_expected)+" 검증":
    "첨부 일부 미보관 "+fmt(post.media_saved)+"/"+fmt(post.media_expected)));
  card.append(meta);
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
  // An unchanged verified ZIP must not be re-downloaded on every tab return.
  // Cache one account/filter's previously rendered DOM for <=90 seconds.
  const previous=state.section;
  if(previous==="posts"&&section!=="posts"&&!state.loading&&
     state.account&&results.querySelector("article.post")&&
     $("more").textContent!=="다시 시도"){
    savedPostsView={account:state.account,filterKey:feedFilterKey(),
      age:performance.now(),nodes:[...results.childNodes],
      offset:state.offset,more:state.more,message:status.textContent};
  }
  const restore=(previous!=="posts"&&section==="posts"&&
     savedPostsView?.account===state.account&&
     savedPostsView.filterKey===feedFilterKey()&&
     performance.now()-savedPostsView.age<=POSTS_VIEW_MAX_AGE_MS);
  // An in-flight response from the old tab must never overwrite the new tab.
  if(state.retryTimer!==null){clearTimeout(state.retryTimer);state.retryTimer=null;}
  state.firstPageRetries=0;
  state.viewVersion+=1;state.loading=false;
  state.section=section;state.offset=0;state.more=false;
  feedSearch.hidden=!journalSection(section);
  $("mastodonActivityControls").hidden=section!=="activity";
  for(const btn of document.querySelectorAll("[data-section]")){
    const active=btn.dataset.section===section;
    if(btn.getAttribute("role")==="tab"){
      btn.classList.toggle("active",active);btn.setAttribute("aria-selected",String(active));
    }
  }
  $("more").hidden=true;$("more").disabled=false;
  if(restore){
    const cached=savedPostsView;
    results.replaceChildren(...cached.nodes);
    state.offset=cached.offset;state.more=cached.more;
    $("more").hidden=!state.more;
    $("more").textContent="더 보기";
    setStatus(cached.message);
    return;
  }
  if(section==="posts")savedPostsView=null;
  showMessage("보관된 "+sectionLabels[section]+" 불러오는 중…");
  if(state.account)void nextPage();
}
async function nextPage(){
  if(state.loading||!state.account)return;
  state.loading=true;$("more").disabled=true;
  const selected=state.section,selectedAccount=state.account,offset=state.offset,
        requestVersion=state.viewVersion;
  try{
    const isJournal=journalSection(selected);
    const feedKindFilter=selected==="replies"?"reply":
      selected==="activity"?$("mastodonActivity").value:
      selected==="featured"?"featured":
      selected==="media"&&state.profile?.platform==="mastodon"&&
        state.profile.show_media_replies===false?"post":
      selected==="media"||selected==="videos"?"":feedKind.value||"post";
    const mediaFilter=selected==="media"?"has_media":
      selected==="videos"?"has_video":feedMediaStatus.value;
    const feedParams=new URLSearchParams({
      offset:String(offset),limit:"20",q:feedQuery.value.trim(),
      kind:feedKindFilter,media_status:mediaFilter});
    const endpoint=isJournal
       ?base()+"/feed?"+feedParams.toString()
       :base()+"/graph/"+selected+"?offset="+offset+"&limit=50";
    const data=await get(endpoint);
    if(state.account!==selectedAccount||state.section!==selected||
       state.viewVersion!==requestVersion)return;
    const records=isJournal?data.posts:data.accounts;
    if(!Array.isArray(records))throw Error("보관본 페이지 형식이 올바르지 않습니다.");
    if(offset===0)results.replaceChildren();
    for(const item of records)results.append(isJournal?postCard(item):personCard(item));
    if(!records.length&&offset===0)
      showMessage(isJournal?"보관된 "+sectionLabels[selected]+"이 없습니다. 백업 실행·완료 여부를 확인하세요.":"조회 가능한 공개 "+sectionLabels[selected]+" 목록이 없습니다.");
    state.offset+=records.length;
    // A stale or malformed cursor cannot create an endless More loop.
    state.more=Boolean(data.more)&&records.length>0&&state.offset>offset;
    $("more").hidden=!state.more;$("more").textContent="더 보기";
    setStatus(isJournal?sectionLabels[selected]+" "+fmt(data.total)+"건 중 "+fmt(state.offset)+"건 표시":
       "공개 관계 계정 "+fmt(data.captured_unique)+"명 보관 · "+fmt(state.offset)+"명 표시 (전체 명단 보장 안 됨)");
  }catch(error){
    if(state.account===selectedAccount&&state.section===selected&&
       state.viewVersion===requestVersion){
      const message=String(error.message||"보관 자료 불러오기 실패");
      // On the free original ZIP reader a returning tab may temporarily
      // receive 502/503/504 while the shared immutable bundle is being
      // read. A bounded retry is better than requiring an operator click;
      // it NEVER treats unverified/failed responses as saved originals.
      const transient=/(?:HTTP (?:502|503|504)|failed to fetch|networkerror)/i.test(message);
      if(offset===0&&journalSection(selected)&&transient&&state.firstPageRetries<4){
        const attempt=++state.firstPageRetries;
        const delay=[1300,3300,7200,13500][attempt-1];
        setStatus("검증된 보관본 읽기 지연 · 자동 복구 "+attempt+"/4");
        state.retryTimer=window.setTimeout(()=>{
          state.retryTimer=null;
          if(state.account===selectedAccount&&state.section===selected&&
             state.viewVersion===requestVersion&&!state.loading)
            void nextPage();
        },delay);
        return;
      }
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
  invalidateSavedPostsView();
  // Cancel stale page and comment renders before changing account.
  state.viewVersion+=1;state.loading=false;
  $("more").hidden=true;$("more").disabled=false;
  detailRequestSeq+=1;
  if(detail.open)detail.close();
  state.account=value||"";state.profile=null;state.offset=0;
  setPlatformTheme(state.account);
  state.section=state.account.startsWith("mastodon-")?"activity":"posts";
  if(value)setAccountUrl(value);
  if(!value){
    resetProfile();$("displayName").textContent="계정을 선택하세요";
    showMessage("계정을 선택하세요.");setStatus("보관할 계정을 선택하세요.");
    return;
  }
  resetProfile();
  showVerifiedPickerPreview(state.accounts.find(item=>item.key===value));
  showMessage("게시글 보관본을 불러오는 중…");
  // The remote profile snapshot can take tens of seconds to verify. Start
  // post loading NOW, independently. A stale profile response must never
  // overwrite a newly selected account.
  setTab(state.section);
  try{
    const profile=await loadVerifiedProfileWithRetry(value);
    if(state.account!==value||profile===null)return;
    renderProfile(profile);
  }catch{
    if(state.account===value){
      // Retain the independently signed picker name/handle on a transient error.
      // Embedded iframe receives a signed account preview from the parent,
      // but state.accounts may be empty. Never overwrite that visible name
      // merely because the private source ZIP had a transient 502.
      $("profileStatus").textContent="원본 프로필 읽기 지연 · 이미지 원본 재확인 필요. 계정을 다시 선택하면 재시도합니다.";
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
    $("retryAccounts").hidden=true;
    renderAccountChoices();
    if(!state.accounts.length){
      const opt=node("option","","아직 보관된 계정 없음");opt.value="";
      accountSelect.append(opt);
      setStatus("등록된 계정 보관본이 없습니다.");
      showMessage("계정 분석에서 공개 계정을 지정해 백업을 시작하세요.");
      return;
    }
    const first=state.accounts.find(a=>a.key===selected)||state.accounts[0];
    accountSelect.value=first.key;
    setStatus("보관된 계정 "+state.accounts.length+"개 · 자동으로 최신 보관본을 표시합니다.");
    await selectAccount(first.key);
  }catch(error){
    const count=$("accountCount");
    if(count)count.textContent="불러오기 실패";
    $("retryAccounts").hidden=false;
    setStatus("계정 목록 연결 실패 · 아래 버튼을 눌러 다시 시도할 수 있습니다.");
    showMessage("개인용 아카이브 서버 인증 또는 저장 연결 상태를 확인하세요.");
  }
}
accountSelect.addEventListener("change",()=>{
  if(ACCOUNT_KEY.test(accountSelect.value))void selectAccount(accountSelect.value);
});
$("accountSearch").addEventListener("input",renderAccountChoices);
$("retryAccounts").addEventListener("click",()=>{
  $("retryAccounts").hidden=true;setStatus("보관 계정 목록을 다시 불러오는 중…");
  void init();
});
feedSearch.addEventListener("submit",event=>{event.preventDefault();resetFeedSearch();});
feedQuery.addEventListener("input",scheduleFeedSearch);
feedKind.addEventListener("change",resetFeedSearch);
feedMediaStatus.addEventListener("change",resetFeedSearch);
$("mastodonActivity").addEventListener("change",()=>{
  if(state.section==="activity")setTab("activity");
});
$("feedReset").addEventListener("click",()=>{
  feedQuery.value="";feedKind.value="";feedMediaStatus.value="";
  resetFeedSearch();
});
document.querySelectorAll("[data-section]").forEach(btn=>btn.addEventListener(
  "click",()=>setTab(btn.dataset.section)));
$("more").addEventListener("click",()=>void nextPage());
$("closeDetail").addEventListener("click",()=>detail.close());
detail.addEventListener("click",event=>{if(event.target===detail)detail.close();});
detail.addEventListener("close",()=>{detailRequestSeq+=1;detailBody.replaceChildren();});
void init();
})();
