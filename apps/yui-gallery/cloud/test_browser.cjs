const {chromium}=require('playwright');
const assert=require('assert');
const tinyPNG=Buffer.from('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVQIHWP4z8DwHwAFgAI/ScL/nwAAAABJRU5ErkJggg==','base64');
const catalog={schema_version:1,albums:[
 {id:'web-set01',title:'Yui 2026 Album A',stored:3,expected:3,quality_label:'public_web_resolution',images:[1,2,3].map(n=>({
  number:n,width:1536,height:2304,key:'originals/web-set01/'+n+'.png',preview:'previews/web-set01/'+n+'.png',sha256:'abc',bytes:100}))
}]};
(async()=>{
 const browser=await chromium.launch({headless:true});
 const page=await browser.newPage({viewport:{width:390,height:844},acceptDownloads:true});
 const errors=[];page.on('pageerror',e=>errors.push(e.message));
 await page.route('https://mock.example/api/**',async route=>{
  const token=route.request().headers()['authorization'];
  if(token!=='Bearer demo-token')return route.fulfill({status:401,body:'Unauthorized',headers:{'access-control-allow-origin':'*'}});
  if(route.request().url().endsWith('/catalog'))return route.fulfill({status:200,contentType:'application/json',body:JSON.stringify(catalog),headers:{'access-control-allow-origin':'*'}});
  return route.fulfill({status:200,contentType:'image/png',body:tinyPNG,headers:{'access-control-allow-origin':'*'}});
 });
 await page.goto('http://127.0.0.1:8765/cloud.html',{waitUntil:'domcontentloaded',timeout:20000});
 assert((await page.locator('#status').textContent()).includes('미연결'));
 await page.locator('#endpoint').fill('https://mock.example');
 await page.locator('#token').fill('demo-token');
 await page.locator('#connect').click();
 await page.waitForFunction(()=>document.querySelector('#status').textContent.includes('연결됨'),{timeout:5000});
 assert.equal(await page.locator('.album').count(),1);
 await page.locator('.album').click();
 assert.equal(await page.locator('.photo').count(),3);
 await page.locator('.photo').first().click();
 await page.waitForFunction(()=>document.querySelector('#full').naturalWidth>0,{timeout:5000});
 const [download]=await Promise.all([page.waitForEvent('download'),page.locator('#download').click()]);
 assert(download.suggestedFilename().startsWith('web-set01-0001'));
 await page.locator('#close').click();
 await page.locator('#back').click();
 await page.selectOption('#sort','new');
 assert.equal(await page.locator('.album').count(),1);
 assert.deepEqual(errors,[]);
 console.log('CLOUD_BROWSER_E2E_PASS',{albumCount:1,fileCount:3,download:download.suggestedFilename(),errors:0});
 await browser.close();
})().catch(e=>{console.error(e.stack);process.exit(1)});
