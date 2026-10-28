/* Mimmi iPhone gallery: only physically saved and actually renderable photos count. */
const fs=require('fs'),path=require('path'),crypto=require('crypto'),vm=require('vm');
const {chromium}=require('playwright');
const root='apps/mimmi-gallery';
const html=fs.readFileSync(path.join(root,'index.html'),'utf8');
const inline=html.match(/<script>([\s\S]*?)<\/script>/);
if(!inline)throw Error('Missing Mimmi gallery script');
new vm.Script(inline[1]);
const index=JSON.parse(fs.readFileSync(path.join(root,'stored-albums.json'),'utf8'));
if(index.model!=='mimmi'||!Array.isArray(index.albums))throw Error('Invalid physical storage manifest');
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
   if(/\/(?:photos|media)\//.test(r.url())&&!r.url().includes('127.0.0.1'))publicPhotoRequests.push(r.url());
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
  if(await cards.count()!==albums.length)throw Error('Displayed album count must equal physical stored albums: '+(await cards.count())+' vs '+albums.length);
  if(await page.locator('#albumgrid [data-id^="research-no-"]').count())throw Error('Research-only photobooks must never appear in gallery');
  const meta=await page.locator('#inventory').innerText();
  if(!meta.includes(images.length+'장 실제 저장'))throw Error('Physical stored count wrong '+meta);
  if(!images.length){
   if(await page.locator('#photogrid .photo').count())throw Error('Unstored photos displayed');
   if(errors.length)throw Error('JS errors '+errors);
   console.log('MIMMI_ZERO_STORED_IMAGES_NO_FAKE_ALBUMS_PASS');
   return;
  }
  const first=albums[0];
  const card=page.locator('#albumgrid [data-id="'+first.id+'"]');
  if(!await card.count())throw Error('Physical album card missing '+first.id);
  await card.click();
  await page.waitForFunction(()=>!document.querySelector('#detail').hidden,{timeout:12000});
  const rendered=await page.locator('#detailphotos .photo').count();
  if(rendered!==first.images.length)throw Error('Only physical photo files count: '+rendered+' vs '+first.images.length);
  await page.locator('#detailphotos .photo').first().click();
  await page.waitForFunction(()=>document.querySelector('#full')?.naturalWidth>100||document.querySelector('#media-status')?.textContent?.includes('불러오지 못'),{timeout:20000});
  if(await page.locator('#full').evaluate(e=>e.naturalWidth)<=100)throw Error('First physically stored photo did not display');
  const src=await page.locator('#full').getAttribute('src');
  if(!src?.startsWith('stored-albums/'))throw Error('Viewer used external photo URL instead of stored bytes: '+src);
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
  console.log('MIMMI_PHYSICALLY_STORED_CHROMIUM_MOBILE_PASS',JSON.stringify({version,albums:albums.length,verifiedFiles:images.length,browserRendered:probe.length}));
 }finally{await browser.close()}
})().catch(e=>{console.error(e.stack||String(e));process.exit(1)});
