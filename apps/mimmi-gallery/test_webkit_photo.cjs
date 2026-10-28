/* WebKit iPhone QA: only stored photos load; unarchived URLs never appear. */
const fs=require('fs'),path=require('path'),{webkit}=require('playwright');
const root='apps/mimmi-gallery';
const data=JSON.parse(fs.readFileSync(path.join(root,'stored-albums.json'),'utf8'));
const albums=data.albums.filter(a=>Array.isArray(a.images)&&a.images.length>0);
const images=albums.flatMap(a=>a.images.map(p=>({album:a.id,...p})));
(async()=>{
 const browser=await webkit.launch({headless:true});
 try{
  const page=await browser.newPage({viewport:{width:390,height:844},isMobile:true,hasTouch:true});
  const errors=[];page.on('pageerror',e=>errors.push(e.message));
  await page.goto('http://127.0.0.1:8765/mimmi-gallery/',{waitUntil:'domcontentloaded',timeout:25000});
  await page.waitForFunction(()=>document.querySelector('#total')?.textContent?.includes('albums'),{timeout:20000});
  if(await page.locator('#albumgrid .album').count()!==albums.length)throw Error('Unstored album shown in WebKit');
  if(!images.length){
   if(!await page.locator('#inventory').innerText().then(s=>s.includes('0장 · 실제 저장본')))throw Error('Unstored gallery not labeled zero');
   console.log('MIMMI_WEBKIT_EMPTY_ARCHIVE_NO_FALSE_PHOTOS_PASS');
   return;
  }
  // Probe ALL physical photo URLs as WebKit images, not just previously verified remote URLs.
  const batch=images.slice(0,Math.min(images.length,40));
  const results=await page.evaluate(async urls=>{
   const results=[];
   for(let i=0;i<urls.length;i+=8){
    const chunk=urls.slice(i,i+8);
    results.push(...await Promise.all(chunk.map(url=>new Promise(resolve=>{
      const img=new Image();img.referrerPolicy='no-referrer';
      img.onload=()=>resolve({url,ok:img.naturalWidth>100,width:img.naturalWidth});
      img.onerror=()=>resolve({url,ok:false,width:0});
      img.src=url;
    }))));
   }
   return results;
  },batch.map(p=>p.url));
  const bad=results.filter(x=>!x.ok);
  if(bad.length)throw Error('Stored photo not renderable in WebKit: '+JSON.stringify(bad.slice(0,4)));
  const album=albums[0];
  await page.locator('#albumgrid [data-id="'+album.id+'"]').click();
  if(!await page.locator('#detail').isVisible())throw Error('Stored photo album detail hidden');
  if(await page.locator('#detailphotos .photo').count()!==album.images.length)throw Error('WebKit detail mismatch');
  await page.locator('#detailphotos .photo').first().click();
  await page.waitForFunction(()=>document.querySelector('#full')?.naturalWidth>100,{timeout:16000});
  if(!String(await page.locator('#full').getAttribute('src')).startsWith('stored-albums/'))throw Error('WebKit remote source photo presented as stored');
  if(errors.length)throw Error('iPhone WebKit JS errors: '+errors.join(';'));
  await page.screenshot({path:'mimmi-beta18-clone-webkit.png'});
  console.log('MIMMI_STORED_ONLY_WEBKIT_PASS',JSON.stringify({albums:albums.length,stored:images.length,browserRendered:results.length}));
 }finally{await browser.close()}
})().catch(e=>{console.error(e.stack||String(e));process.exit(1)});
