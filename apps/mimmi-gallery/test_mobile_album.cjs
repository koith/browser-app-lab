/* Real mobile Chromium browser test: model navigation, photo-first Mimmi
   album experience, no broken-image placeholder glyphs, real image decoding. */
const fs=require('fs');
const vm=require('vm');
const { chromium }=require('playwright');
const root='apps/mimmi-gallery/';
const html=fs.readFileSync(root+'index.html','utf8');
const match=html.match(/<script>([\s\S]*?)<\/script>/);
if(!match)throw Error('Inline UI script missing');
new vm.Script(match[1]);
if(!html.includes('v0.1.0-mimmi.4'))throw Error('App version missing');
const official=JSON.parse(fs.readFileSync(root+'official-previews.json'));
const actor=JSON.parse(fs.readFileSync(root+'v2ph-actor-previews.json'));
const secondary=JSON.parse(fs.readFileSync(root+'v2ph-public-previews.json'));
const inventory=JSON.parse(fs.readFileSync(root+'research-catalogue.json'));
if(official.albums.length<32||inventory.works.length<50||actor.albums.length<30)throw Error('Lost existing source data');
const unique=new Set([...official.albums,...actor.albums,...secondary.albums].flatMap(a=>(a.samples||[]).map(s=>s.sha256)));
if(unique.size<390)throw Error('Missing validated public photo source metadata: '+unique.size);

(async()=>{
 const browser=await chromium.launch({headless:true});
 try{
  const page=await browser.newPage({viewport:{width:390,height:844},isMobile:true,hasTouch:true});
  const errors=[];page.on('pageerror',e=>errors.push(e.message));
  await page.goto('http://127.0.0.1:8765/mimmi-gallery/',{waitUntil:'domcontentloaded'});
  await page.waitForFunction(()=>document.querySelector('#summary')?.textContent.includes('개 화보'),{timeout:25000});
  const link=page.locator('#yui-link');
  if(await link.getAttribute('target')!=='_blank')throw Error('Yui gallery must open new tab');
  if(await link.getAttribute('rel')!=='noopener noreferrer')throw Error('External tab security missing');
  const yuiUrl=await link.evaluate(x=>x.href);
  if(!yuiUrl.endsWith('/apps/yui-gallery/')&&!yuiUrl.endsWith('/yui-gallery/'))throw Error('Yui href wrong: '+yuiUrl);
  const [separateTab]=await Promise.all([page.waitForEvent('popup',{timeout:12000}),link.click()]);
  await separateTab.waitForLoadState('domcontentloaded',{timeout:15000});
  if(!separateTab.url().includes('/yui-gallery/'))throw Error('Yui new tab opened wrong URL: '+separateTab.url());
  if(!page.url().includes('/mimmi-gallery/'))throw Error('Mimmi tab was replaced rather than preserved');
  await separateTab.close();
  if(!await page.locator('#app-version').isVisible())throw Error('Version label invisible');
  const version=await page.locator('#app-version').innerText();
  if(version!=='v0.1.0-mimmi.4')throw Error('Wrong Mimmi version');
  const bbox=await page.locator('#app-version').boundingBox();
  if(!bbox||bbox.height>15||bbox.x<270||bbox.y>14)throw Error('Version not small in upper right: '+JSON.stringify(bbox));
  const cards=page.locator('.album');
  await cards.first().waitFor();
  const total=await cards.count();
  if(total<35)throw Error('Too few Mimmi albums: '+total);
  if(await cards.first().locator('.photos').count())throw Error('All thumbnails are expanded on album list');
  const title=await cards.first().locator('.album-title').innerText();
  // Browser QA checks actual individual image decoding, not just URL candidates.
  await cards.first().locator('.cover').scrollIntoViewIfNeeded();
  await page.waitForFunction(()=>{
   const tile=document.querySelector('.album .cover');
   if(!tile)return false;
   const image=tile.querySelector('img');
   const fallback=tile.querySelector('.cover-fallback');
   return (image&&image.complete&&image.naturalWidth>=100)||(fallback&&!fallback.hidden);
  },{timeout:22000});
  const coverState=await cards.first().locator('.cover').evaluate(node=>({
   loaded:!!node.querySelector('img')&&node.querySelector('img').naturalWidth>100,
   fallback:!!node.querySelector('.cover-fallback')&&!node.querySelector('.cover-fallback').hidden,
   broken:!!node.querySelector('img')&&node.querySelector('img').complete&&node.querySelector('img').naturalWidth===0
  }));
  if(coverState.broken)throw Error('Broken image icon is visible');
  const tileRect=await cards.first().locator('.cover').boundingBox();
  const cardRect=await cards.first().boundingBox();
  if(!tileRect||tileRect.height>350||!cardRect||cardRect.height>470)throw Error('Oversized album card reintroduces screenshot bug: '+JSON.stringify({tileRect,cardRect}));
  await cards.first().locator('.album-open').click();
  if(!await page.locator('#album-detail').isVisible())throw Error('Album details not open');
  if(await page.locator('#overview').isVisible())throw Error('Album list not hidden');
  const tileCount=await page.locator('.photo-tile').count();
  if(tileCount<3)throw Error('Photo tiles missing on album detail');
  await page.locator('.photo-tile').first().click();
  if(!await page.locator('#viewer').isVisible())throw Error('Fullscreen photo not open');
  await page.waitForFunction(()=>{
   const img=document.querySelector('#viewer-image'),error=document.querySelector('#viewer-error');
   return (img&&!img.hidden&&img.complete&&img.naturalWidth>100)||(error&&!error.hidden);
  },{timeout:20000});
  const full=await page.locator('#viewer-image').evaluate(x=>({w:x.naturalWidth,hidden:x.hidden}));
  if(full.w<=100){
   console.log('MIMMI_SOURCE_HOST_BLOCKED_IN_THIS_RUN',title);
   const source=await page.locator('#viewer-origin').getAttribute('href');
   if(!source?.startsWith('https://'))throw Error('Source fallback invalid');
  }
  await page.locator('#viewer-next').click();
  if(!(await page.locator('#viewer-position').innerText()).startsWith('2 /'))throw Error('Next photo navigation failed');
  await page.locator('#viewer-close').click();
  await page.locator('#back').click();
  await page.waitForFunction(()=>!document.querySelector('#overview').hidden,{timeout:8000});
  await page.locator('#search').fill('Elegg');
  if(await page.locator('.album').count()<1)throw Error('Search broken');
  await page.locator('#search').fill('');
  await page.locator('#filter-all').click();
  if(await page.locator('#filter-all').getAttribute('aria-pressed')!=='true')throw Error('All albums filter broken');
  const overflow=await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth+2);
  if(overflow)throw Error('Mobile layout horizontally overflows');
  if(errors.length)throw Error('JS exceptions: '+errors.join(';'));
  await page.screenshot({path:'mimmi-mobile-v4.png',fullPage:false});
  console.log('MIMMI_PHOTO_FIRST_MOBILE_PASS',{
   version,photoSetCount:total,firstCover:coverState,firstFullWidth:full.w,
   firstAlbumPhotos:tileCount,uniqueSourceImages:unique.size,yuiOpensNewTab:true
  });
 }finally{await browser.close()}
})().catch(e=>{console.error(e.stack||String(e));process.exit(1)});
