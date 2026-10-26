// Integration QA: the private viewer reads actual nested ZIP bytes in mobile Chromium.
const fs=require('fs'),crypto=require('crypto'),JSZip=require('jszip');
const {chromium}=require('playwright');
const png=Buffer.from('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVQIHWP4z8DwHwAFgAI/ScL/nwAAAABJRU5ErkJggg==','base64');
async function makeAlbum(id,count,corrupt=false){
 const z=new JSZip(),images=[];
 for(let i=1;i<=count;i++){
  const file=String(i).padStart(3,'0')+'.png';
  z.file('images/'+file,png);
  images.push({n:i,file,sha256:corrupt?'0'.repeat(64):crypto.createHash('sha256').update(png).digest('hex'),bytes:png.length,width:700,height:1000});
 }
 z.file('manifest.json',JSON.stringify({id,title:id,advertised_count:count,images}));
 return z.generateAsync({type:'nodebuffer'});
}
(async()=>{
 const outer=new JSZip();
 outer.file('teddy-bear97.zip',await makeAlbum('teddy-bear97',2));
 outer.file('v04_public_web_album.zip',await makeAlbum('v04',2));
 outer.file('green91_public_web_album.zip',await makeAlbum('green91',1));
 const data=await outer.generateAsync({type:'nodebuffer'});
 const browser=await chromium.launch({headless:true});
 try{
  const page=await browser.newPage({viewport:{width:390,height:844},acceptDownloads:true});
  const errors=[];page.on('pageerror',e=>errors.push(e.message));
  await page.route('https://cdn.jsdelivr.net/npm/jszip@3.10.1/dist/jszip.min.js',route=>route.fulfill({contentType:'application/javascript',body:fs.readFileSync(require.resolve('jszip/dist/jszip.min.js'))}));
  await page.goto('http://127.0.0.1:8765/zip-gallery.html',{waitUntil:'load'});
  await page.locator('#files').setInputFiles({name:'nested-archive.zip',mimeType:'application/zip',buffer:data});
  await page.waitForFunction(()=>document.querySelector('#summary').textContent.includes('3장'),{timeout:15000});
  const summary=await page.locator('#summary').innerText();
  if(!summary.includes('2개 화보'))throw Error('Duplicate album counted twice: '+summary);
  if(await page.locator('.album').count()!==2)throw Error('Wrong photobook card count');
  await page.locator('[data-open="teddy-bear97"]').click();
  if(await page.locator('.tile').count()!==2)throw Error('Missing complete album files');
  await page.locator('.tile').first().click();
  await page.waitForFunction(()=>document.querySelector('#full').naturalWidth>0,{timeout:9000});
  const [download]=await Promise.all([page.waitForEvent('download'),page.locator('#download').click()]);
  if(!download.suggestedFilename().endsWith('.png'))throw Error('Bad actual photo download');
  await page.locator('#close').click();
  await page.locator('#back').click();
  const broken=await makeAlbum('bad-album',1,true);
  await page.locator('#files').setInputFiles({name:'corrupted.zip',mimeType:'application/zip',buffer:broken});
  await page.waitForFunction(()=>document.querySelector('#status').textContent.includes('실패'),{timeout:9000});
  if(await page.locator('.album').count()!==2)throw Error('Corrupt file entered archive');
  if(errors.length)throw Error('JavaScript errors: '+errors.join(';'));
  console.log('YUI_PRIVATE_ZIP_VIEWER_E2E_PASS',{summary,files:3,corruption_rejected:true,photo_download:download.suggestedFilename()});
 }finally{await browser.close()}
})().catch(e=>{console.error(e.stack);process.exit(1)});
