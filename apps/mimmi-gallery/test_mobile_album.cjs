/* Mimmi iPhone gallery: only physically saved and actually renderable photos count. */
const fs=require('fs'),path=require('path'),crypto=require('crypto'),vm=require('vm');
const {chromium}=require('playwright');
const root='apps/mimmi-gallery';
const html=fs.readFileSync(path.join(root,'index.html'),'utf8');
const inline=html.match(/<script>([\s\S]*?)<\/script>/);
if(!inline)throw Error('Missing Mimmi gallery script');
new vm.Script(inline[1]);
const index=JSON.parse(fs.readFileSync(path.join(root,'stored-albums.json'),'utf8'));
if((index.model&&index.model!=='mimmi')||!Array.isArray(index.albums))throw Error('Invalid physical storage manifest');
const albums=index.albums.filter(a=>a.images?.length);
const images=albums.flatMap(a=>a.images.map(p=>({album:a.id,...p})));
for(const p of images){
 if(!new RegExp('^stored-albums/'+p.album+'/[a-zA-Z0-9._-]+\\.(?:jpe?g|png|webp|avif)$').test(p.url))throw Error('Nonlocal source counted as stored '+p.url);
 const f=path.join(root,p.url);
 if(!fs.existsSync(f))throw Error('Gallery is falsely claiming missing physical file '+p.url);
 const buf=fs.readFileSync(f);
 if(buf.length!==p.bytes||crypto.createHash('sha256').update(buf).digest('hex')!==p.sha256)throw Error('Physically stored file integrity mismatch '+p.url);
}
if(index.physical_verified_image_count!==undefined&&index.physical_verified_image_count!==images.length)throw Error('Stored index count mismatch');
(async()=>{
 const browser=await chromium.launch({headless:true});
 try{
  const page=await browser.newPage({viewport:{width:390,height:844},isMobile:true,hasTouch:true});
  const errors=[];page.on('pageerror',e=>errors.push(e.message));
  const publicPhotoRequests=[];
  page.on('request',r=>{
   if(/\/(?:photos|media)\//.test(r.url())&&!r.url().includes('127.0.0.1')&&new URL(r.url()).hostname!=='mimmi-private-gallery-free.onrender.com')publicPhotoRequests.push(r.url());
  });
  await page.goto('http://127.0.0.1:8765/mimmi-gallery/',{waitUntil:'domcontentloaded',timeout:25000});
  await page.waitForFunction(()=>document.querySelector('#total')?.textContent?.includes('albums'),{timeout:20000});
  const version=await page.locator('#app-version').innerText();
  if(!version.startsWith('v0.1.0-mimmi.'))throw Error('Invalid version '+version);
  const yui=page.locator('.mainnav a').first();
  if(await yui.getAttribute('target')!=='_blank')throw Error('Yui gallery must open in a new tab');
  const [popup]=await Promise.all([page.waitForEvent('popup',{timeout:12000}),yui.click()]);
  if(!popup.url().includes('yui-gallery'))throw Error('Cross-model tab selection failed');
  await popup.close();
  const cards=page.locator('#albumgrid .album');
  const runtime=await page.evaluate(()=>({
    albums:available().length,
    photos:stored.reduce((n,a)=>n+validImages(a).length,0),
    duplicates:stored.reduce((n,a)=>{
      const sha=validImages(a).map(p=>p.sha256);
      return n+sha.length-new Set(sha).size;
    },0)
  }));
  if(runtime.duplicates)throw Error('Identical image SHA displayed repeatedly: '+runtime.duplicates);
  if(await cards.count()!==runtime.albums)throw Error('Rendered cards mismatch saved owner+local album manifest: '+(await cards.count())+' vs '+runtime.albums);
  if(await page.locator('#albumgrid [data-id^="research-no-"]').count())throw Error('Research-only photobooks must never appear in gallery');
  const meta=await page.locator('#inventory').innerText();
  if(!meta.includes(runtime.photos+'장 · 실제 저장본'))throw Error('Saved local+owner unique image count wrong '+meta);
  if(await page.locator('#device-health').count())throw Error('Yui-style header must not show technical image health');
  if(await page.locator('#browse-mode').innerText()!=='화보')throw Error('Yui-style gallery must default to album view');
  const viewport=await page.evaluate(()=>({columns:getComputedStyle(document.querySelector('#albumgrid')).gridTemplateColumns.split(' ').length,
    logo:document.querySelector('.logo span')?.getClientRects().length||0}));
  if(viewport.columns!==2||!viewport.logo)throw Error('Yui beta.19 iPhone layout mismatch '+JSON.stringify(viewport));
  if(!images.length && !runtime.photos){
   if(await page.locator('#photogrid .photo').count())throw Error('Unstored photos displayed');
   if(errors.length)throw Error('JS errors '+errors);
   console.log('MIMMI_ZERO_STORED_IMAGES_NO_FAKE_ALBUMS_PASS');
   return;
  }
  // Exercise a *real local file*, not a sleeping private-cloud API endpoint.
  const publicAlbum=await page.evaluate(()=>{
    const a=stored.find(x=>validImages(x).some(p=>p.url?.startsWith('stored-albums/')));
    return a?.id||null;
  });
  if(!publicAlbum)throw Error('No physical public image to check in the gallery');
  const card=page.locator('#albumgrid [data-id="'+publicAlbum+'"]');
  if(!await card.count())throw Error('Saved public album card missing '+publicAlbum);
  await card.click();
  await page.waitForFunction(()=>!document.querySelector('#detail').hidden,{timeout:12000});
  const actual=await page.evaluate(id=>validImages(stored.find(x=>x.id===id)).length,publicAlbum);
  const rendered=await page.locator('#detailphotos .photo').count();
  if(rendered!==actual)throw Error('Rendered photo count mismatch: '+rendered+' vs '+actual);
  const localPhoto=page.locator('#detailphotos .photo:has(img[src^="stored-albums/"])').first();
  if(!await localPhoto.count())throw Error('Gallery did not expose physical public photo');
  await localPhoto.click();
  await page.waitForFunction(()=>document.querySelector('#full')?.naturalWidth>100||document.querySelector('#media-status')?.textContent?.includes('불러오지 못'),{timeout:20000});
  if(await page.locator('#full').evaluate(e=>e.naturalWidth)<=100)throw Error('Saved public photo did not decode in browser');
  const src=await page.locator('#full').getAttribute('src');
  if(!src?.startsWith('stored-albums/'))throw Error('Expected physically stored static file: '+src);
  await page.locator('#close').click();
  await page.locator('#back').click();
  await page.locator('#browse-toggle').click();
  if(!await page.locator('#publishergrid').isVisible())throw Error('Publisher grouping navigation broken');
  await page.locator('#browse-toggle').click();
  const probe=images.slice(0,Math.min(16,images.length));
  const failures=await page.evaluate(async urls=>{
   const out=[];
   for(const url of urls){
    const img=new Image();img.referrerPolicy='no-referrer';
    const result=await new Promise(resolve=>{
      img.onload=()=>resolve(img.naturalWidth>100);
      img.onerror=()=>resolve(false);
      img.src=url;
    });
    if(!result)out.push(url);
   }
   return out;
  },probe.map(p=>p.url));
  if(failures.length)throw Error('Physical photos failed browser render: '+failures.slice(0,4));
  if(publicPhotoRequests.length)throw Error('Gallery requested external research-only media: '+publicPhotoRequests.slice(0,3));
  if(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth+2))throw Error('Mobile overflow');
  if(errors.length)throw Error('JS exceptions: '+errors.join('; '));
  await page.screenshot({path:'mimmi-beta18-clone-chromium.png'});
  console.log('MIMMI_PHYSICALLY_STORED_CHROMIUM_MOBILE_PASS',JSON.stringify({version,albums:runtime.albums,uniqueVisiblePhotos:runtime.photos,verifiedPublicFiles:images.length,browserRendered:probe.length}));
 }finally{await browser.close()}
})().catch(e=>{console.error(e.stack||String(e));process.exit(1)});
