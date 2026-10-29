/* Smoke actual imported original image bytes in Chromium and iPhone WebKit. */
'use strict';
const {chromium,webkit}=require('playwright');
const {readFileSync}=require('node:fs');
const {join}=require('node:path');
// Compute expected physical gallery images from committed evidence; harvest workflows
// continuously add files, so fixed numbers must never make QA stale.
function physicalCount(model){
 const path=join(__dirname,model+'-gallery','stored-albums.json');
 const data=JSON.parse(readFileSync(path,'utf8'));
 if(!Array.isArray(data.albums))throw Error('Invalid physical manifest '+model);
 const images=data.albums.flatMap(a=>a.images||[]);
 if(!images.every(p=>typeof p.url==='string'&&p.url.startsWith('stored-albums/')&&/^[a-f0-9]{64}$/.test(p.sha256||'')))
   throw Error('Non-local or unverified image in '+model+' public manifest');
 return images.length;
}
const baselines={yui:physicalCount('yui'),mimmi:physicalCount('mimmi')};

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
   // Import a second partial archive of the SAME work. The first photo must survive.
   if(await page.locator('#vault-file').getAttribute('multiple')===null)throw Error('Multi-ZIP selection not enabled');
   await page.locator('#vault-file').setInputFiles([
     importName,
     '/tmp/photo-vault-qa/'+model+'-incremental.zip'
   ]);
   await page.waitForFunction(n=>document.querySelector('#inventory')?.textContent?.startsWith(n+'장'),baseline+2,{timeout:15000});
   if(!(await page.locator('#vault-status').innerText()).includes('검증 완료 ZIP 2 / 2개'))
     throw Error('Multi-ZIP import confirmation was lost on reload');
   const expanded=await page.evaluate(async m=>PhotoVault.albums(m).then(rows=>rows.find(a=>a.id==='vault-fixture-'+m)),model);
   if(!expanded||expanded.images.length!==2||expanded.images[0].number!==1||expanded.images[1].number!==2)
     throw Error('Incremental ZIP overwrote previous photos or collapsed duplicate SHA positions');
   // The same two numbered photos must survive a compressed Actions wrapper ZIP.
   // The wrapper has no root manifest and contains two nested private-import ZIPs.
   await Promise.all([
     page.waitForEvent('framenavigated',{timeout:25000}),
     page.locator('#vault-file').setInputFiles('/tmp/photo-vault-qa/'+model+'-actions.zip')
   ]);
   await page.waitForFunction(n=>document.querySelector('#inventory')?.textContent?.startsWith(n+'장'),baseline+2,{timeout:15000});
   const wrapped=await page.evaluate(async m=>PhotoVault.albums(m).then(rows=>rows.find(a=>a.id==='vault-fixture-'+m)),model);
   if(!wrapped||wrapped.images.length!==2||wrapped.images[0].number!==1||wrapped.images[1].number!==2)
     throw Error('Actions wrapper ZIP import did not preserve numbered image positions');
   // Reimporting an older partial ZIP must not erase the additional second photo.
   await Promise.all([
     page.waitForEvent('framenavigated',{timeout:25000}),
     page.locator('#vault-file').setInputFiles(importName)
   ]);
   // Import success triggers its own navigation. Do not call reload concurrently.
   await page.waitForFunction(n=>document.querySelector('#inventory')?.textContent?.startsWith(n+'장'),baseline+2,{timeout:15000});
   await page.locator('#vault-file').setInputFiles('/tmp/photo-vault-qa/'+model+'-corrupt.zip');
   await page.waitForFunction(()=>document.querySelector('#vault-status')?.textContent?.includes('가져오기 실패'),{timeout:15000});
   if((await page.locator('#inventory').innerText()).startsWith((baseline+3)+'장'))throw Error('Corrupt ZIP was counted');
   // When a private SHA-verified copy overlaps an already committed physical
   // cover/photo position, prefer its Blob but count that position only once.
   await Promise.all([
     page.waitForEvent('framenavigated',{timeout:25000}),
     page.locator('#vault-file').setInputFiles('/tmp/photo-vault-qa/'+model+'-overlap.zip')
   ]);
   await page.waitForFunction(n=>document.querySelector('#inventory')?.textContent?.startsWith(n+'장'),baseline+2,{timeout:15000});
   const originalAlbum=JSON.parse(readFileSync(join(__dirname,model+'-gallery','stored-albums.json'),'utf8')).albums.find(a=>a.images?.some(p=>p.url?.startsWith('stored-albums/')));
   await page.locator('#albumgrid [data-id="'+originalAlbum.id+'"]').click();
   await page.waitForFunction(()=>!document.querySelector('#detail').hidden);
   await page.waitForFunction(()=>document.querySelector('#detailphotos .photo img')?.src?.startsWith('blob:'),{timeout:15000});
   // A corrupt ZIP in a multi-selection must not prevent another valid ZIP
   // from being imported and reported after the navigation.
   await page.goto('http://127.0.0.1:8765/'+model+'-gallery/');
   await Promise.all([
     page.waitForEvent('framenavigated',{timeout:25000}),
     page.locator('#vault-file').setInputFiles([
       '/tmp/photo-vault-qa/'+model+'-corrupt.zip',
       '/tmp/photo-vault-qa/'+model+'-overlap.zip'
     ])
   ]);
   // Inventory was already baseline+2 before this re-import. Wait for the
   // post-navigation *completed summary*, not a stale counter or in-flight text.
   await page.waitForFunction(()=>document.querySelector('#vault-status')?.textContent?.includes('검증 완료 ZIP 1 / 2개'),{timeout:20000});
   const mixedResult=await page.locator('#vault-status').innerText();
   if(!mixedResult.includes('검증 완료 ZIP 1 / 2개')||!mixedResult.includes('실패 1개'))
     throw Error('Mixed-validity ZIP batch did not preserve partial-success feedback: '+mixedResult);

   if((await page.locator('#detailphotos .photo img').first().getAttribute('src'))?.startsWith('http'))
     throw Error('Saved private photo was shadowed by a public preview');

  }
  await open('yui',baselines.yui);
  await importOne('yui',baselines.yui);
  await open('mimmi',baselines.mimmi);
  if(await page.locator('#albumgrid [data-id="vault-fixture-yui"]').count())throw Error('Cross-model private vault leakage');
  await importOne('mimmi',baselines.mimmi);
  await page.goto('http://127.0.0.1:8765/yui-gallery/');
  await page.waitForFunction(n=>document.querySelector('#inventory')?.textContent?.startsWith(n+'장'),baselines.yui+2);
  if(errors.length||external.length)throw Error('Browser errors or source media requested '+JSON.stringify({errors,external:external.slice(0,5)}));
  console.log('TWO_MODELS_SHA_VERIFIED_ZIP_IMPORT_'+engineName.toUpperCase()+'_PASS',JSON.stringify({yui:baselines.yui+2,mimmi:baselines.mimmi+2,persistent:true,incrementalMerged:true,duplicateShaNumbersKept:true,nestedActionsZip:true,physicalOverlapPrefersPrivate:true,multiZipImport:true,mixedValidityBatches:true,corruptRejected:true,externalImageRequests:0}));
 }finally{await browser.close()}
})().catch(e=>{console.error(e.stack||e);process.exit(1)});
