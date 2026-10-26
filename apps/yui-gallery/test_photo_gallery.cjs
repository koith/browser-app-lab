const {chromium}=require('playwright');
const fs=require('fs'),crypto=require('crypto'),JSZip=require('jszip');
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
  await page.route('https://cdn.jsdelivr.net/npm/jszip@3.10.1/dist/jszip.min.js',route=>route.fulfill({contentType:'application/javascript',body:fs.readFileSync(require.resolve('jszip/dist/jszip.min.js'))}));
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
  await page.locator('[data-view="photos"]').click();

  // No setup wall: importing a private ZIP occurs through one small header action.
  const tinyPNG=Buffer.from('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVQIHWP4z8DwHwAFgAI/ScL/nwAAAABJRU5ErkJggg==','base64');
  const inner=new JSZip();
  inner.file('images/001.png',tinyPNG);
  inner.file('images/002.png',tinyPNG);
  inner.file('manifest.json',JSON.stringify({id:'v04',advertised_count:2,images:[1,2].map(n=>({number:n,file:String(n).padStart(3,'0')+'.png',bytes:tinyPNG.length,sha256:crypto.createHash('sha256').update(tinyPNG).digest('hex'),width:700,height:1000}))}));
  const outer=new JSZip();outer.file('v04_public_web_album.zip',await inner.generateAsync({type:'nodebuffer'}));
  const archive=await outer.generateAsync({type:'nodebuffer'});
  await page.locator('#files').setInputFiles({name:'my-album.zip',mimeType:'application/zip',buffer:archive});
  await page.waitForFunction(()=>document.querySelector('#notice').textContent.includes('2장 불러왔습니다'),{timeout:15000});
  const imported=await page.locator('.photo-card').count();
  if(imported!==physical-10+2)throw Error('Duplicate incomplete Teddy preview not replaced: '+imported);
  await page.locator('.photo-card').first().click();
  await page.waitForFunction(()=>document.querySelector('#large').naturalWidth>0,{timeout:8000});
  await page.locator('#close').click();

  const corrupt=new JSZip();const wrong={id:'bad-album',advertised_count:1,images:[{number:1,file:'001.png',bytes:tinyPNG.length,sha256:'0'.repeat(64),width:700,height:1000}]};
  corrupt.file('manifest.json',JSON.stringify(wrong));corrupt.file('images/001.png',tinyPNG);
  await page.locator('#files').setInputFiles({name:'bad.zip',mimeType:'application/zip',buffer:await corrupt.generateAsync({type:'nodebuffer'})});
  await page.waitForFunction(()=>document.querySelector('#notice').textContent.includes('일부 오류'),{timeout:12000});
  if(await page.locator('.photo-card').count()!==imported)throw Error('Corrupt ZIP added photos');
  if(errors.length)throw Error('JS errors '+JSON.stringify(errors));
  console.log('YUI_PHOTO_FIRST_MOBILE_E2E_PASS',{physical,gridImages:count,importedPhotos:2,importRejectedCorruption:true,download:download.suggestedFilename(),errors:0});
 }finally{await browser.close()}
})().catch(e=>{console.error(e.stack);process.exit(1)});
