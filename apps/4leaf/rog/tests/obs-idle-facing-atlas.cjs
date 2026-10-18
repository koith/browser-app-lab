'use strict';
/* Audit recovered exact-source OBS frames; never invent face directions.
 * Screenshot the SAME scaleY(-1) native PNG orientation the real board uses.
 */
const assert=require('node:assert/strict');
const {chromium}=require('playwright');
(async()=>{
 const browser=await chromium.launch({headless:true,args:['--no-sandbox']});
 try{
  const page=await browser.newPage({viewport:{width:1440,height:1200},deviceScaleFactor:1});
  await page.goto('http://127.0.0.1:8765/index.html');
  await page.waitForFunction(()=>window.ORIGINAL_LEAF_OBS_FRAMES&&window.__LEAF_GENESIS_ACTORS__);
  const report=await page.evaluate(async()=>{
   const ids=['0042','0043','0044','0045','0054','0078','0079','0080'];
   const root=document.createElement('main');
   root.id='obs-face-atlas';
   root.style.cssText='position:absolute;inset:0 auto auto 0;z-index:99999;background:#d3dccb;color:#12203c;padding:18px;width:1320px;display:grid;grid-template-columns:repeat(8,156px);gap:6px;font:13px monospace;box-sizing:border-box';
   const load=[];
   const candidates={};
   for(const id of ids){
    const o=window.ORIGINAL_LEAF_OBS_FRAMES[id];
    if(!o){candidates[id]=[];continue}
    candidates[id]=o.frames.map(f=>f.index);
    for(const f of o.frames){
     const card=document.createElement('div');
     card.style.cssText='box-sizing:border-box;height:206px;padding:5px;background:#b4c7b3;border:1px solid #80907d;text-align:center';
     const label=document.createElement('div');
     label.textContent=id+' · '+String(f.index).padStart(2,'0')+' ('+f.width+'×'+f.height+')';
     const stage=document.createElement('div');
     stage.style.cssText='position:relative;height:166px;display:flex;align-items:center;justify-content:center';
     const img=document.createElement('img');
     img.src=f.url;
     img.style.cssText='width:'+f.width*1.65+'px;height:'+f.height*1.65+'px;image-rendering:pixelated;transform:scaleY(-1);object-fit:contain';
     stage.append(img);card.append(label,stage);root.append(card);
     load.push(img.decode().catch(e=>String(e)));
    }
   }
   document.body.replaceChildren(root);
   await Promise.all(load);
   return {candidates,total:load.length,loaded:root.querySelectorAll('img').length};
  });
  assert.ok(report.total>=30,JSON.stringify(report));
  await page.locator('#obs-face-atlas').screenshot({path:'leaf-obs-source-facing-atlas.png'});
  console.log('ORIGINAL OBS FRAME FACE ATLAS SOURCE-ONLY',JSON.stringify(report));
 }finally{await browser.close()}
})().catch(e=>{console.error('OBS FACE ATLAS FAILED',e.stack||e);process.exit(1)});
