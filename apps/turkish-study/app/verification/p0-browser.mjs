// Owner 03 reproducible browser verification, NOT executed yet.
// From a clone: npm install --no-save playwright; npx playwright install chromium webkit
// node apps/turkish-study/app/verification/p0-browser.mjs
// No tracked data/manifest edits. Approved manifest is served only on isolated localhost in memory.
import { chromium, webkit } from "playwright";
import { createServer } from "node:http";
import { readFile } from "node:fs/promises";
import { resolve, dirname, extname, sep } from "node:path";
import { fileURLToPath } from "node:url";
import assert from "node:assert/strict";
const root=resolve(dirname(fileURLToPath(import.meta.url)),"../..");
const m=JSON.parse(await readFile(resolve(root,"RELEASE_MANIFEST.json"),"utf8"));
const lessons=JSON.parse(await readFile(resolve(root,"lessons.json"),"utf8")).lessons;
const approved={...m,stage:"published",releaseId:"TEST-ONLY",contentRevision:"fixture-only",verifiedAt:new Date().toISOString(),publishedDayIds:m.candidateDayIds};
let fixture=false;
const srv=createServer(async (req,res)=>{
 try{
  const u=new URL(req.url,"http://localhost"), path=resolve(root,"."+ (u.pathname==="/" ? "/index.html":u.pathname));
  if(!path.startsWith(root+sep)){res.writeHead(403).end();return;}
  const data=u.pathname==="/RELEASE_MANIFEST.json"&&fixture?JSON.stringify(approved):await readFile(path);
  const type={".html":"text/html; charset=utf-8",".json":"application/json",".js":"text/javascript",".webmanifest":"application/manifest+json",".svg":"image/svg+xml"}[extname(path)]||"application/octet-stream";
  res.writeHead(200,{"Content-Type":type,"Cache-Control":"no-store"}).end(data);
 }catch{res.writeHead(404).end();}
});
await new Promise(r=>srv.listen(0,"127.0.0.1",r));
const base="http://127.0.0.1:"+srv.address().port+"/";
const results=[];
try{
for(const [name,engine] of Object.entries({chromium,webkit})){
 let browser;
 try{
  browser=await engine.launch();
  const context=await browser.newContext({viewport:{width:390,height:844},acceptDownloads:true});
  fixture=false;
  const page=await context.newPage(),errors=[];
  page.on("pageerror",e=>errors.push(e.message));page.on("dialog",d=>d.accept());
  const key="turkce120-v1";
  const state=()=>page.evaluate(k=>JSON.parse(localStorage.getItem(k)),key);
  const check=(scope)=>results.push({browser:name,scope,result:"pass"});
  await page.goto(base);await page.getByText("공개 승인 대기",{exact:true}).first().waitFor();
  await page.locator('button[data-tab="course"]').click();
  assert.equal(await page.locator("#quiz").count(),0);check("live manifest locks lessons and quiz");
  fixture=true;await page.reload();await page.getByRole("button",{name:"학습 시작"}).waitFor();await page.getByRole("button",{name:"학습 시작"}).click();
  assert.equal(await page.locator("#quiz").count(),1);
  assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth<=window.innerWidth),true);check("390px layout and approved lesson");
  const questions=lessons[0].questions;
  for(const q of questions){await page.locator('input[name="'+q.id+'"]').first().check();}
  // explicitly choose wrong and then correct choices using DOM values rather than labels.
  for(const q of questions)await page.locator('input[name="'+q.id+'"]').evaluateAll((nodes,answer)=>{const wrong=nodes.find(n=>n.value!==answer);wrong.click()},q.answer);
  await page.getByRole("button",{name:"시험 제출"}).click();assert.equal((await state()).a.attempts.at(-1).score,0);
  await page.getByRole("button",{name:"수업 완료",exact:true}).click();assert.equal((await state()).a.done[1],undefined);check("incorrect score and completion rejection");
  for(const q of questions)await page.locator('input[name="'+q.id+'"]').evaluateAll((nodes,answer)=>nodes.find(n=>n.value===answer).click(),q.answer);
  await page.getByRole("button",{name:"시험 제출"}).click();await page.getByRole("button",{name:"수업 완료",exact:true}).click();
  assert.equal((await state()).a.attempts.at(-1).score,100);assert.ok((await state()).a.done[1]);check("correct score and completion");
  await page.locator('button[data-tab="review"]').click();await page.locator("summary").first().click();
  await page.getByRole("button",{name:"쉬움",exact:true}).first().click();assert.equal((await state()).a.cards["D001-V1"].stage,2);check("SRS");
  await page.locator('button[data-tab="words"]').click();await page.locator('button[data-action="favorite:D001-V1"]').click();assert.equal((await state()).a.cards["D001-V1"].favorite,true);
  await page.locator("#profile").selectOption("b");assert.deepEqual((await state()).b.done,{});assert.equal((await state()).b.attempts.length,0);check("two profiles");
  await page.locator('button[data-tab="settings"]').click();const dl=page.waitForEvent("download");await page.getByRole("button",{name:"백업 내보내기"}).click();
  const download=await dl, path=await download.path();assert.ok(path);const bytes=await readFile(path);
  // Confirm persisted record before test-only deletion.
  await page.reload();await page.getByRole("button",{name:"학습 시작"}).waitFor();assert.ok((await state()).a.done[1]);check("reload persistence");
  await page.evaluate(k=>localStorage.removeItem(k),key);await page.reload();await page.getByRole("button",{name:"학습 시작"}).waitFor();
  await page.locator('button[data-tab="settings"]').click();await page.locator("#import").setInputFiles({name:"test-backup.json",mimeType:"application/json",buffer:bytes});
  await page.waitForFunction(k=>Boolean(JSON.parse(localStorage.getItem(k))?.a?.done?.[1]),key);
  assert.equal((await state()).a.cards["D001-V1"].favorite,true);assert.deepEqual((await state()).b.done,{});check("real file backup and import");
  if(await page.evaluate(()=>Boolean(navigator.serviceWorker))){
   await page.evaluate(()=>navigator.serviceWorker.ready.then(()=>true));
   await page.reload();await page.getByRole("button",{name:"학습 시작"}).waitFor();
   await context.setOffline(true);await page.reload();await page.getByText(/오프라인 캐시/).waitFor();check("offline shell and coherent snapshot");
   await context.setOffline(false);
  }
  fixture=false;await page.reload();await page.getByRole("button",{name:"공개 승인 대기"}).waitFor();await page.locator('button[data-tab="course"]').click();
  assert.equal(await page.locator("#quiz").count(),0);assert.ok((await state()).a.done[1]);check("approval revocation preserved records");
  assert.deepEqual(errors,[]);check("no page errors");
  await context.close();
 }catch(e){results.push({browser:name,result:"fail",error:String(e)});}
 finally{if(browser)await browser.close();}
}
}finally{srv.close();}
console.log(JSON.stringify({environment:"localhost browser automation; WebKit is not physical iPhone Safari",results},null,2));
if(results.some(r=>r.result==="fail"))process.exitCode=1;
