/* Mimmi latest-Yui-beta.18 clone, album-level navigation and real public previews. */
const fs=require('fs'),vm=require('vm'),{chromium}=require('playwright');
const root='apps/mimmi-gallery/';
const html=fs.readFileSync(root+'index.html','utf8');
const inline=html.match(/<script>([\s\S]*?)<\/script>/);
if(!inline)throw Error('Mimmi beta18 inline app missing');
new vm.Script(inline[1]);
const manifest=JSON.parse(fs.readFileSync(root+'source-viewer-albums.json'));
const count=manifest.albums.reduce((n,a)=>n+a.images.length,0);
if(manifest.albums.length<45||count<395||!manifest.source_link_only)throw Error('Insufficient source-viewer image evidence '+count);
const hashes=manifest.albums.flatMap(a=>a.images.map(p=>p.sha256));
if(new Set(hashes).size!==count)throw Error('Source image bytes repeat across albums');
if(manifest.albums.some(a=>a.expected&&a.images.length>a.expected))throw Error('Album overclaimed');
(async()=>{
 const browser=await chromium.launch({headless:true});
 try{
  const page=await browser.newPage({viewport:{width:390,height:844},isMobile:true,hasTouch:true});
  const errors=[];page.on('pageerror',x=>errors.push(x.message));
  await page.goto('http://127.0.0.1:8765/mimmi-gallery/',{waitUntil:'domcontentloaded',timeout:25000});
  await page.waitForFunction(()=>document.querySelector('#total')?.textContent?.includes('albums'),{timeout:20000});
  const version=await page.locator('#app-version').innerText();
  if(version!=='v0.1.0-mimmi.5')throw Error('Wrong version '+version);
  const pos=await page.locator('#app-version').boundingBox();
  if(!pos||pos.y>25||pos.height>20||pos.x<180)throw Error('Version not small upper-right '+JSON.stringify(pos));
  const yui=page.locator('.mainnav a').first();
  if(await yui.getAttribute('target')!=='_blank'||!String(await yui.getAttribute('href')).includes('../yui-gallery/'))throw Error('Yui must open in new tab');
  const [popup]=await Promise.all([page.waitForEvent('popup',{timeout:12000}),yui.click()]);
  await popup.waitForLoadState('domcontentloaded',{timeout:12000});
  if(!popup.url().includes('/yui-gallery/')||!page.url().includes('/mimmi-gallery/'))throw Error('Cross-model tab navigation failed');
  await popup.close();
  const albumCards=await page.locator('#albumgrid .album').count();
  if(albumCards<105)throw Error('Incomplete album cards '+albumCards);
  if(await page.locator('#albumgrid .photo').count())throw Error('Old giant expanded card gallery still present');
  const first=page.locator('#albumgrid .album').first();
  const box=await first.boundingBox();
  if(!box||box.height>420)throw Error('Album card too large for mobile '+JSON.stringify(box));
  // Official publisher photos should be normal page images, with readable fallback
  // if a remote host blocks hotlinking on an iPhone.
  const official=page.locator('#albumgrid [data-id="djawa-in-the-summer-sunshine-part-2"]');
  await official.click();
  if(!await page.locator('#detail').isVisible())throw Error('Album detail hidden');
  const officialCount=await page.locator('#detailphotos .photo').count();
  if(officialCount<6||officialCount>24)throw Error('Unexpected official public promo count '+officialCount);
  await page.locator('#detailphotos .photo').first().click();
  await page.waitForFunction(()=>{
    const image=document.querySelector('#full'),message=document.querySelector('#media-status');
    return (image?.complete&&image?.naturalWidth>100)||message?.textContent.includes('불러오지 못');
  },{timeout:20000});
  await page.locator('#next').click();
  if(!(await page.locator('#position').innerText()).startsWith('2 /'))throw Error('Photo arrow failed');
  // Safari history gesture equivalent: viewer → album → overview.
  await page.goBack({waitUntil:'domcontentloaded'});
  await page.waitForFunction(()=>!document.querySelector('#detail').hidden&&!document.querySelector('#lightbox').classList.contains('open'),{timeout:12000});
  await page.goBack({waitUntil:'domcontentloaded'});
  await page.waitForFunction(()=>!document.querySelector('#browse').hidden,{timeout:12000});
  if(!await page.locator('#albumgrid [data-id="research-no-052"]').count())throw Error('Missing research set NO.052 on newest clone');
  await page.goForward({waitUntil:'domcontentloaded'});
  await page.waitForFunction(()=>!document.querySelector('#detail').hidden,{timeout:12000});
  await page.goForward({waitUntil:'domcontentloaded'});
  await page.waitForFunction(()=>document.querySelector('#lightbox').classList.contains('open'),{timeout:12000});
  await page.locator('#close').click();
  await page.waitForFunction(()=>!document.querySelector('#lightbox').classList.contains('open'),{timeout:12000});
  await page.locator('#back').click();
  await page.waitForFunction(()=>!document.querySelector('#browse').hidden,{timeout:12000});
  const v2ph=page.locator('#albumgrid [data-id="v2ph-cream-cow-milk"]');
  await v2ph.click();
  const partial=await page.locator('#albumtotal').innerText();
  if(!/^[0-9]+장 \/ 164장 · 누락 [0-9]+장$/.test(partial))throw Error('Lying about incomplete 164-photo album '+partial);
  await page.locator('#back').click();
  await page.locator('#browse-toggle').click();
  if(!await page.locator('#publishergrid').isVisible())throw Error('Latest publisher switch broken');
  if(await page.locator('#publishergrid .publisher').count()<2)throw Error('Publisher list missing');
  await page.locator('#browse-toggle').click();
  const overflow=await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth+2);
  if(overflow)throw Error('Mobile horizontal overflow');
  if(errors.length)throw Error('JS exceptions: '+errors.join(';'));
  await page.screenshot({path:'mimmi-beta18-clone-chromium.png'});
  console.log('MIMMI_LATEST_YUI_CLONE_MOBILE_PASS',{version,albums:albumCards,photos:count,officialCount,partial,modelTab:true,safariBackForward:true});
 }finally{await browser.close()}
})().catch(e=>{console.error(e.stack||String(e));process.exit(1)});
