/* iPhone-like WebKit test of latest gallery and original-host link reliability. */
const fs=require('fs'),{webkit}=require('playwright');
const root='apps/mimmi-gallery/';
const albums=JSON.parse(fs.readFileSync(root+'source-viewer-albums.json')).albums;
const official=albums.find(a=>a.id==='djawa-in-the-summer-sunshine-part-2');
const v2ph=albums.find(a=>a.id==='v2ph-cream-cow-milk');
async function probe(page,url,policy){return page.evaluate(async ({url,policy})=>new Promise(resolve=>{
 const image=new Image();image.referrerPolicy=policy;
 const end=v=>resolve({...v,origin:url.split('/')[2]});
 image.onload=()=>end({ok:image.naturalWidth>100,width:image.naturalWidth});
 image.onerror=()=>end({ok:false,reason:'onerror'});
 image.src=url;setTimeout(()=>end({ok:false,reason:'timeout'}),10000);
 }),{url,policy})}
(async()=>{
 const browser=await webkit.launch({headless:true});
 try{
  const page=await browser.newPage({viewport:{width:390,height:844},isMobile:true,hasTouch:true});
  const exceptions=[];page.on('pageerror',e=>exceptions.push(e.message));
  await page.goto('http://127.0.0.1:8765/mimmi-gallery/',{waitUntil:'domcontentloaded',timeout:20000});
  await page.waitForFunction(()=>document.querySelector('#total')?.textContent.includes('albums'),{timeout:20000});
  const health=[];
  for(const a of [official,v2ph]){
   for(const policy of ['no-referrer','origin']){
    health.push({id:a.id,policy,...await probe(page,a.images[0].url,policy)});
   }
  }
  const card=page.locator('#albumgrid [data-id="djawa-in-the-summer-sunshine-part-2"]');
  await card.click();
  if(!await page.locator('#detail').isVisible())throw Error('Missing latest photo detail view');
  if(await page.locator('#detailphotos .photo').count()!==6)throw Error('Wrong DJAWA sample count');
  await page.locator('#detailphotos .photo').first().click();
  await page.waitForFunction(()=>{
   const image=document.querySelector('#full'),status=document.querySelector('#media-status');
   return (image?.complete&&image?.naturalWidth>100)||status?.textContent.includes('불러오지 못');
  },{timeout:20000});
  const loaded=await page.locator('#full').evaluate(x=>x.naturalWidth>100);
  if(!loaded&&!String(await page.locator('#media-status').innerText()).includes('불러오지 못'))throw Error('Broken image without failure message');
  const brokenIcons=await page.locator('.album.broken-source img:not([hidden]),.photo.broken-source img:not([hidden])').count();
  if(brokenIcons)throw Error('Broken source icons are visible');
  if(exceptions.length)throw Error('WebKit JavaScript exception: '+exceptions.join(';'));
  await page.screenshot({path:'mimmi-beta18-clone-webkit.png',fullPage:false});
  console.log('MIMMI_BETA18_WEBKIT_PASS',JSON.stringify({health,loaded,errors:exceptions.length}));
 }finally{await browser.close()}
})().catch(e=>{console.error(e.stack||String(e));process.exit(1)});
