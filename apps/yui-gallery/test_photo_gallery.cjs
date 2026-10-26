const {chromium}=require('playwright');
const fs=require('fs'),crypto=require('crypto');
(async()=>{
 const base='apps/yui-gallery/';
 const catalog=JSON.parse(fs.readFileSync(base+'stored-albums.json','utf8'));
 let physical=0;
 for(const a of catalog.albums||[])for(const p of a.images||[]){
   const b=fs.readFileSync(base+p.url);
   if(b.length!==p.bytes||crypto.createHash('sha256').update(b).digest('hex')!==p.sha256)throw Error('Bad image byte/hash '+p.url);
   physical++;
 }
 const browser=await chromium.launch({headless:true});
 try{
  const page=await browser.newPage({viewport:{width:390,height:844},isMobile:true,hasTouch:true,acceptDownloads:true});
  const errors=[];page.on('pageerror',e=>errors.push(e.message));
  await page.goto('http://127.0.0.1:8765/',{waitUntil:'domcontentloaded'});
  await page.waitForFunction(()=>document.querySelectorAll('.photo-card').length>0,{timeout:15000});
  const count=await page.locator('.photo-card').count();
  if(count!==physical)throw Error('Photo-first view missing physical assets '+count+' vs '+physical);
  if(await page.locator('.photo-card img').first().evaluate(i=>i.naturalWidth)===0)
    await page.waitForFunction(()=>document.querySelector('.photo-card img').naturalWidth>0,{timeout:8000});
  if(await page.locator('.photo-card img').first().evaluate(i=>i.naturalWidth)===0)throw Error('First photo not physically rendered');
  if(await page.locator('.panel').count()!==0)throw Error('Unexpected setup panel in primary gallery');
  await page.locator('.photo-card').first().click();
  await page.waitForFunction(()=>document.querySelector('#large').naturalWidth>0,{timeout:8000});
  if(!(await page.locator('#position').innerText()).includes('1 /'))throw Error('Viewer numbering missing');
  await page.locator('#next').click();
  if(!(await page.locator('#position').innerText()).includes('2 /'))throw Error('Viewer forward navigation broken');
  await page.locator('#prev').click();
  const [download]=await Promise.all([page.waitForEvent('download'),page.locator('#save').click()]);
  if(!download.suggestedFilename().startsWith('cn-')&&!download.suggestedFilename().includes('v04'))throw Error('File download name invalid');
  await page.locator('#close').click();
  await page.locator('[data-view="albums"]').click();
  if(await page.locator('.album-card').count()<1)throw Error('Album thumbnails missing');
  await page.locator('.album-card').first().click();
  if(await page.locator('.photo-card').count()<1)throw Error('Album photos not shown');
  await page.locator('[data-view="sns"]').click();
  if(errors.length)throw Error('JS errors '+JSON.stringify(errors));
  console.log('YUI_PHOTO_FIRST_MOBILE_E2E_PASS',{physical,gridImages:count,download:download.suggestedFilename(),errors:0});
 }finally{await browser.close()}
})().catch(e=>{console.error(e.stack);process.exit(1)});
