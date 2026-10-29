/* Smoke actual imported original image bytes in Chromium and iPhone WebKit. */
'use strict';
const {chromium,webkit}=require('playwright');
const engineName=process.argv[2]||'chromium';
const engine={chromium,webkit}[engineName];if(!engine)throw Error('Unknown engine');
(async()=>{
 const browser=await engine.launch({headless:true});
 try{
  const ctx=await browser.newContext({viewport:{width:390,height:844},isMobile:true,hasTouch:true,acceptDownloads:true});
  const page=await ctx.newPage(),errors=[],external=[];
  page.on('pageerror',e=>errors.push(e.message));
  page.on('request',r=>{if(r.resourceType()==='image'&&!r.url().startsWith('http://127.0.0.1:8765/')&&!r.url().startsWith('blob:'))external.push(r.url())});
  async function open(model,baseline){
   await page.goto('http://127.0.0.1:8765/'+model+'-gallery/',{waitUntil:'domcontentloaded',timeout:30000});
   await page.waitForFunction(()=>document.querySelector('#inventory')?.textContent?.includes('실제 저장본'),{timeout:20000});
   const current=await page.locator('#inventory').innerText();
   if(!current.startsWith(baseline+'장'))throw Error('Baseline not saved physical count '+model+' '+current);
  }
  async function importOne(model,baseline){
   const importName='/tmp/photo-vault-qa/'+model+'-good.zip';
   await page.locator('#vault-file').setInputFiles(importName);
   try{await page.waitForFunction(n=>document.querySelector('#inventory')?.textContent?.startsWith(n+'장'),baseline+1,{timeout:30000})}catch(error){throw Error('Import did not appear: '+model+' '+engineName+' status='+await page.locator('#vault-status').innerText()+' inventory='+await page.locator('#inventory').innerText()+' errors='+JSON.stringify(errors)+' cause='+error.message)}
   if(await page.locator('#albumgrid [data-id="vault-fixture-'+model+'"]').count()!==1)throw Error('Imported album not shown '+model);
   await page.locator('#albumgrid [data-id="vault-fixture-'+model+'"]').click();
   await page.waitForFunction(()=>!document.querySelector('#detail').hidden);
   if(await page.locator('#detailphotos .photo').count()!==1)throw Error('Wrong imported photo count');
   await page.locator('#detailphotos .photo').first().click();
   await page.waitForFunction(()=>document.querySelector('#full')?.naturalWidth>100,{timeout:12000});
   const src=await page.locator('#full').getAttribute('src');
   if(!src?.startsWith('blob:'))throw Error('Not a physical local Blob viewer: '+src);
   await page.goto('http://127.0.0.1:8765/'+model+'-gallery/');
   await page.waitForFunction(n=>document.querySelector('#inventory')?.textContent?.startsWith(n+'장'),baseline+1);
   const saved=await page.evaluate(async m=>PhotoVault.albums(m).then(rows=>rows.filter(a=>a.id==='vault-fixture-'+m)),model);
   if(saved.length!==1||saved[0].images.length!==1)throw Error('IndexedDB persistence failed');
   await page.locator('#vault-file').setInputFiles('/tmp/photo-vault-qa/'+model+'-corrupt.zip');
   await page.waitForFunction(()=>document.querySelector('#vault-status')?.textContent?.includes('가져오기 실패'),{timeout:15000});
   if((await page.locator('#inventory').innerText()).startsWith((baseline+2)+'장'))throw Error('Corrupt ZIP was counted');
  }
  await open('yui',23);
  await importOne('yui',23);
  await open('mimmi',2162);
  if(await page.locator('#albumgrid [data-id="vault-fixture-yui"]').count())throw Error('Cross-model private vault leakage');
  await importOne('mimmi',2162);
  await page.goto('http://127.0.0.1:8765/yui-gallery/');
  await page.waitForFunction(()=>document.querySelector('#inventory')?.textContent?.startsWith('24장'));
  if(errors.length||external.length)throw Error('Browser errors or source media requested '+JSON.stringify({errors,external:external.slice(0,5)}));
  console.log('TWO_MODELS_SHA_VERIFIED_ZIP_IMPORT_'+engineName.toUpperCase()+'_PASS',JSON.stringify({yui:24,mimmi:2163,persistent:true,corruptRejected:true,externalImageRequests:0}));
 }finally{await browser.close()}
})().catch(e=>{console.error(e.stack||e);process.exit(1)});
