'use strict';
// Source-source registration of recovered KnightTown/knightback.png against
// the first 142x74 frame of each original KnightTown 568x74 sign sheet.
// These six original atlases are source artwork, not complete screenshots.
const assert=require('node:assert/strict');
const {chromium}=require('playwright');
(async()=>{
 const browser=await chromium.launch({headless:true,args:['--no-sandbox']});
 const page=await browser.newPage({viewport:{width:1280,height:850}});
 try{
  await page.goto(process.env.FOURLEAF_TEST_URL||'http://127.0.0.1:8765/');
  await page.waitForFunction(()=>window.__LEAF_KNIGHT_TOWN__);
  const matches=await page.evaluate(async()=>{
   const areas=window.__LEAF_KNIGHT_TOWN__.getState().areas;
   const load=async path=>{const img=new Image();img.src=path;await img.decode();return img};
   const imagePixels=image=>{
    const canvas=document.createElement('canvas');canvas.width=image.naturalWidth;canvas.height=image.naturalHeight;
    const ctx=canvas.getContext('2d',{willReadFrequently:true});ctx.drawImage(image,0,0);
    return ctx.getImageData(0,0,canvas.width,canvas.height).data;
   };
   const backdrop=await load('./original/KnightTown/knightback.png');
   const raw=imagePixels(backdrop),BW=backdrop.naturalWidth;
   const output=[];
   for(const area of areas){
    const sprite=await load('./original/KnightTown/'+area.asset+'.png');
    if(sprite.naturalWidth!==568||sprite.naturalHeight!==74)throw Error('Atlas size '+area.asset);
    const atlas=imagePixels(sprite),SW=sprite.naturalWidth;
    const samples=[];
    for(let y=3;y<73;y+=4)for(let x=3;x<141;x+=4){
     const i=(y*SW+x)*4;
     const r=atlas[i],g=atlas[i+1],b=atlas[i+2],a=atlas[i+3];
     if(a<180||g>=210&&r<80&&b<95)continue;
     samples.push([x,y,r,g,b]);
    }
    const nearest=[];
    const original=area.sprite;
    for(let y=Math.max(0,original[1]-46);y<=Math.min(404-74,original[1]+46);y++){
     for(let x=Math.max(0,original[0]-54);x<=Math.min(BW-142,original[0]+54);x++){
      let sum=0;
      for(const [sx,sy,r,g,b] of samples){
       const p=((y+sy)*BW+x+sx)*4;
       // Robust RGB clip avoids unrepresentative fully saturated matte
       // while retaining the actual archive pixels for registration.
       sum+=Math.min(150,Math.abs(raw[p]-r))+
         Math.min(150,Math.abs(raw[p+1]-g))+
         Math.min(150,Math.abs(raw[p+2]-b));
      }
      nearest.push({x,y,score:sum/(samples.length*3)});
     }
    }
    nearest.sort((a,b)=>a.score-b.score||a.y-b.y||a.x-b.x);
    const proposed=nearest[0];
    const current=nearest.find(v=>v.x===original[0]&&v.y===original[1])||null;
    output.push({area:area.id,label:area.name,original,
     aligned:[proposed.x,proposed.y],meanRGB:proposed.score,
     atOld:current?.score??null,margin:nearest[1]?.score-proposed.score,
     samples:samples.length,source:[sprite.naturalWidth,sprite.naturalHeight]});
   }
   return output;
  });
  assert.equal(matches.length,6,'six independently recovered region sign atlases');
  for(const m of matches){
   assert.ok(m.samples>200,'original sign has enough opaque source samples: '+m.area);
   assert.deepEqual(m.source,[568,74],'original four 142x74 atlas states');
   console.log('ORIGINAL KNIGHT SIGN REGISTRATION',JSON.stringify(m));
  }
 }finally{await browser.close()}
})().catch(e=>{console.error('SOURCE SIGN CORRELATION FAILED',e.stack||e);process.exit(1)});
