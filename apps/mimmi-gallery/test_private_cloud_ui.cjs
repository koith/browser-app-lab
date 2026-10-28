/* Safari-like private gateway configuration and owner session QA. */
const fs=require('fs'),vm=require('vm'),{webkit}=require('playwright');
const pageHtml=fs.readFileSync('apps/mimmi-gallery/cloud.html','utf8');
const inline=pageHtml.match(/<script>([\s\S]*?)<\/script>/);
if(!inline)throw Error('Missing connection form controller');
new vm.Script(inline[1]);
(async()=>{
 const browser=await webkit.launch({headless:true});
 try{
  const page=await browser.newPage({viewport:{width:390,height:844},isMobile:true,hasTouch:true});
  const errors=[];page.on('pageerror',e=>errors.push(e.message));
  await page.goto('http://127.0.0.1:8765/mimmi-gallery/cloud.html',{waitUntil:'domcontentloaded'});
  if(!await page.locator('#connect').isVisible())throw Error('Missing private connection form');
  await page.locator('#api').fill('http://open-insecure.example');
  await page.locator('#token').fill('secret-test-token');
  await page.locator('button[type=submit]').click();
  if(!String(await page.locator('#status').innerText()).includes('HTTPS'))throw Error('Unsafe HTTP accepted');
  const before=await page.evaluate(()=>sessionStorage.getItem('mimmi-owner-session'));
  if(before)throw Error('Invalid session persisted');
  await page.route('https://archive-test.example/api/catalog',async route=>{
   if(route.request().method()==='OPTIONS')
    await route.fulfill({status:204,headers:{'access-control-allow-origin':'http://127.0.0.1:8765','access-control-allow-methods':'GET, OPTIONS','access-control-allow-headers':'authorization'}});
   else {
    if(route.request().headers()['authorization']!=='Bearer secret-test-token')
      throw Error('Missing authenticated request header');
    await route.fulfill({status:200,contentType:'application/json',headers:{'access-control-allow-origin':'http://127.0.0.1:8765'},
       body:JSON.stringify({schema_version:1,model:'mimmi',albums:[{id:'valid',images:[{number:1}]}]})});
   }
  });
  await page.locator('#api').fill('https://archive-test.example/');
  await page.locator('button[type=submit]').click();
  await page.waitForURL('**/mimmi-gallery/',{timeout:10000});
  const state=await page.evaluate(()=>JSON.parse(sessionStorage.getItem('mimmi-owner-session')||'null'));
  if(!state||state.api!=='https://archive-test.example'||state.token!=='secret-test-token')
   throw Error('Authenticated session missing');
  if(page.url().includes('secret-test-token'))throw Error('Token exposed in URL');
  if(errors.length)throw Error(errors.join(';'));
  console.log('MIMMI_WEBKIT_PRIVATE_CLOUD_UI_PASS',{session:true,noTokenInURL:true});
 }finally{await browser.close()}
})().catch(e=>{console.error(e.stack||String(e));process.exit(1)});
