/* Browser-engine check approximating iOS Safari. Source-hosted media
   must never show a broken-image glyph, even if CDN hotlinking fails. */
const fs=require('fs');
const {webkit}=require('playwright');
const folder='apps/mimmi-gallery/';
const official=JSON.parse(fs.readFileSync(folder+'official-previews.json','utf8'));
const actor=JSON.parse(fs.readFileSync(folder+'v2ph-actor-previews.json','utf8'));
const secondary=JSON.parse(fs.readFileSync(folder+'v2ph-public-previews.json','utf8'));
const seeds=[
 {type:'official',url:official.albums[0].samples[0].url},
 {type:'official',url:official.albums[1].samples[0].url},
 {type:'v2ph-actor',url:actor.albums[0].samples[0].url},
 {type:'v2ph-seed',url:secondary.albums[0].samples[0].url}
];
async function probe(page,url,policy){
 return await page.evaluate(async ({url,policy})=>new Promise(resolve=>{
  const img=new Image();
  img.referrerPolicy=policy; img.onload=()=>resolve({ok:img.naturalWidth>=100,width:img.naturalWidth,height:img.naturalHeight});
  img.onerror=()=>resolve({ok:false,width:0,error:'onerror'});
  img.src=url;
  setTimeout(()=>resolve({ok:false,error:'timeout'}),10000);
 }),{url,policy});
}
(async()=>{
 const browser=await webkit.launch({headless:true});
 try{
  const page=await browser.newPage({viewport:{width:390,height:844},isMobile:true,hasTouch:true});
  const errs=[];page.on('pageerror',err=>errs.push(err.message));
  await page.goto('http://127.0.0.1:8765/mimmi-gallery/',{waitUntil:'domcontentloaded'});
  await page.waitForFunction(()=>document.querySelector('#summary')?.textContent.includes('개 화보'),{timeout:30000});
  if(await page.locator('#yui-link').getAttribute('target')!=='_blank')throw Error('Yui not new tab');
  const result=[];
  for(const item of seeds){
   const no=await probe(page,item.url,'no-referrer');
   const origin=await probe(page,item.url,'origin');
   const strict=await probe(page,item.url,'strict-origin-when-cross-origin');
   result.push({type:item.type,noReferrer:no,origin,strict});
  }
  console.log('MIMMI_WEBKIT_CDN_HOST_HEALTH',JSON.stringify(result));
  const card=page.locator('.album').first();
  await card.locator('.album-open').click();
  if(!await page.locator('#album-detail').isVisible())throw Error('WebKit album detail hidden');
  await page.locator('.photo-tile').first().click();
  if(!await page.locator('#viewer').isVisible())throw Error('WebKit fullscreen hidden');
  await page.waitForFunction(()=>{
   const img=document.querySelector('#viewer-image'),error=document.querySelector('#viewer-error');
   return (!!img&&!img.hidden&&img.naturalWidth>100)||(!!error&&!error.hidden);
  },{timeout:20000});
  const imageWidth=await page.locator('#viewer-image').evaluate(x=>x.naturalWidth);
  if(imageWidth<=100&&!await page.locator('#viewer-error').isVisible())throw Error('Broken image without readable fallback in Safari');
  if(errs.length)throw Error('WebKit app exceptions: '+errs.join(';'));
  await page.screenshot({path:'mimmi-webkit-v5.png',fullPage:false});
  console.log('MIMMI_WEBKIT_MOBILE_QA_PASS',JSON.stringify({imageWidth,firstAlbum:await page.locator('#detail-title').innerText()}));
 }finally{await browser.close()}
})().catch(e=>{console.error(e.stack||String(e));process.exit(1)});
