/* Read-only verified original archive. Never loads external SNS media as a substitute.
 * All dynamic content is textContent / DOM nodes, never raw HTML.
 */
(function(){
"use strict";
const $=id=>document.getElementById(id);
const list=$("posts"),status=$("status"),more=$("more");
const state={offset:0,total:0,busy:false,generation:0};
function node(tag,className,value){
  const el=document.createElement(tag);
  if(className)el.className=className;
  if(value!==undefined&&value!==null)el.textContent=String(value);
  return el;
}
function safeRemote(url){
  if(typeof url!=="string"||url.length>2048)return "";
  try{
    const u=new URL(url);
    if(u.protocol!=="https:"||u.username||u.password||u.hash)return "";
    return u.href;
  }catch{return "";}
}
function archivedMediaUrl(raw){
  if(typeof raw!=="string"||raw.length>500)return "";
  try{
    const u=new URL(raw,location.origin);
    if(u.origin!==location.origin||!/^\/api\/media\/[a-f0-9]{16,64}\/[0-9]+$/.test(u.pathname))
      return "";
    if(!u.searchParams.has("exp")||!u.searchParams.has("sig"))return "";
    return u.pathname+u.search;
  }catch{return "";}
}
function link(url,text,download=false){
  const a=node("a","",text);
  a.href=url;
  if(download)a.setAttribute("download","");
  else{a.target="_blank";a.rel="noopener noreferrer";}
  return a;
}
function displayDate(value){
  const d=new Date(value);
  return Number.isFinite(d.getTime())?d.toLocaleString("ko-KR"):"작성 시각 미확인";
}
function mediaView(item){
  if(!item||item.verified!==true)return null;
  const url=archivedMediaUrl(item.url);
  if(!url)return null;
  const mime=String(item.mime||"");
  const box=node("figure","media");
  let content;
  if(mime.startsWith("image/")){
    content=node("img");content.alt="테라박스에 저장된 원본 이미지";
    content.loading="lazy";content.decoding="async";content.src=url;
  }else if(mime.startsWith("video/")){
    content=node("video");content.controls=true;content.playsInline=true;
    content.preload="metadata";content.src=url;
  }else if(mime.startsWith("audio/")){
    content=node("audio");content.controls=true;content.preload="none";content.src=url;
  }else{return null;}
  box.append(content);
  const caption=node("figcaption");
  caption.append(node("span","",mime+" · "+Math.round(Number(item.bytes||0)/1024)+" KB"),
                 link(url,"원본 파일 열기"));
  box.append(caption);
  return box;
}
function postCard(post){
  const card=node("article","post");
  const head=node("div","post-head");
  const name={bluesky:"Bluesky",mastodon:"Mastodon",
              misskey:"Misskey",lemmy:"Lemmy"}[post.platform]||"SNS";
  head.append(node("strong","",name+" · 저장된 게시글"),
              node("time","",displayDate(post.posted_at)));
  card.append(head,node("p","post-body",post.text||"(본문 없음)"));
  const media=node("div","post-medias");
  for(const item of Array.isArray(post.media)?post.media:[]){
    const component=mediaView(item);if(component)media.append(component);
  }
  if(media.children.length)card.append(media);
  const saved=Number(post.media_saved||0),expected=Number(post.media_expected||0);
  const partial=post.capture_status!=="remote_verified"||saved<expected;
  const meta=node("p","post-meta"+(partial?" partial":""),
    "원본 첨부 "+saved+"/"+expected+"개"+(partial?" · 미보관 원본 있음":" · 보관 확인"));
  card.append(meta);
  const urls=node("div","post-links");
  const original=safeRemote(post.source_url),profile=safeRemote(post.profile_url);
  if(original)urls.append(link(original,"SNS 원문으로 이동"));
  if(profile)urls.append(link(profile,"작성자 프로필"));
  if(urls.children.length)card.append(urls);
  return card;
}
function params(){
  return new URLSearchParams({
    offset:String(state.offset),limit:"20",q:$("query").value.trim(),
    platform:$("platform").value,media_status:$("mediaStatus").value});
}
async function load(reset){
  if(state.busy)return;
  if(reset){state.generation++;state.offset=0;state.total=0;list.replaceChildren();}
  const version=state.generation,offset=state.offset;
  state.busy=true;more.disabled=true;more.hidden=true;
  status.textContent="테라박스 보관본을 확인 중입니다…";
  try{
    const response=await fetch("/api/posts?"+params(),{
      credentials:"same-origin",cache:"no-store",headers:{Accept:"application/json"}});
    if(!response.ok)throw Error("저장된 원본을 불러오지 못했습니다 (HTTP "+response.status+")");
    const result=await response.json();
    if(version!==state.generation)return;
    if(!Array.isArray(result.posts)||!Number.isFinite(Number(result.total)))
      throw Error("보관본 목록 형식이 올바르지 않습니다.");
    for(const row of result.posts)list.append(postCard(row));
    state.offset+=result.posts.length;
    state.total=Number(result.total);
    if(!state.offset)list.append(node("p","empty",
      "확인된 보관본이 없습니다. 수집 작업과 테라박스 저장 상태를 확인해 주세요."));
    status.textContent="검증된 게시글 "+state.total.toLocaleString("ko-KR")+
      "건 중 "+state.offset.toLocaleString("ko-KR")+"건 표시";
    more.hidden=state.offset>=state.total||!result.posts.length;
    more.textContent="더 보기 ("+(state.total-state.offset)+"건 남음)";
  }catch(error){
    if(!state.offset)list.replaceChildren(node("p","empty",String(error.message)));
    status.textContent="보관본 조회 실패 · 새로 검색하거나 다시 시도해 주세요.";
    more.hidden=false;more.textContent="다시 시도";
  }finally{state.busy=false;more.disabled=false;}
}
$("search").addEventListener("submit",event=>{event.preventDefault();void load(true);});
more.addEventListener("click",()=>void load(false));
void load(true);
})();