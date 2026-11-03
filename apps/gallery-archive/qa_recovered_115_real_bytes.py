#!/usr/bin/env python3
"""Verify every recovered Pages photo can be fetched, SHA checked and decoded.

This browser test deliberately blocks Render: recovered files must be actual
GitHub Pages assets, not a source-site hotlink or a private gateway request.
"""
import argparse
import json
from playwright.sync_api import sync_playwright

PAGE="https://koith.github.io/browser-app-lab/apps/mimmi-gallery/"


def run(browser):
    context=browser.new_context(viewport={"width":390,"height":844},
                                is_mobile=True,has_touch=True,locale="ko-KR")
    page=context.new_page()
    page.route("**/*onrender.com/**",lambda r:r.abort("blockedbyclient"))
    page.goto(PAGE,wait_until="domcontentloaded",timeout=60000)
    page.wait_for_function(
        "()=>typeof stored!=='undefined' && Array.isArray(stored) && stored.length>0 && Array.isArray(localStored)",
        timeout=90000)
    result=page.evaluate("""async()=>{
      const manifest=await fetch('number-collision-distinct.json',{cache:'no-store'}).then(r=>{
        if(!r.ok)throw Error('manifest http '+r.status);
        return r.json();
      });
      const expected=new Set(manifest.photos.map(p=>p.album+'|'+p.sha256));
      const displayed=new Set(stored.flatMap(a=>a.images.map(p=>p.sha256)));
      // SHA-union (PR #545) retired collisionRecovered; using that old flag
      // creates a false 90-second timeout. Verify each historic SHA is BOTH
      // displayed in the current union and still a real saved Pages file.
      const rows=manifest.photos.map(record=>{
        const album=localStored.find(a=>a.id===record.album);
        const photo=album?.images.find(p=>p.sha256===record.sha256);
        if(!photo || !displayed.has(record.sha256))
          throw Error('Historical SHA missing from physical store or gallery');
        return {album:record.album,sha256:record.sha256,url:photo.url,
                width:photo.width,height:photo.height};
      });
      if(expected.size!==115||rows.length!==115||
         rows.some(p=>!expected.has(p.album+'|'+p.sha256)))
         throw Error('Missing, unreviewed or duplicate recovered image');
      let cursor=0;const failures=[];let decoded=0,shaVerified=0,totalBytes=0;
      const toHex=buf=>[...new Uint8Array(buf)].map(x=>x.toString(16).padStart(2,'0')).join('');
      async function check(row){
        const source=new URL(row.url,location.href);
        if(source.origin!==location.origin||
           !source.pathname.startsWith('/browser-app-lab/apps/mimmi-gallery/stored-albums/'))
           throw Error('nonlocal recovered file url');
        const response=await fetch(source.href,{cache:'no-store'});
        if(!response.ok)throw Error('photo HTTP '+response.status);
        const raw=await response.arrayBuffer();
        totalBytes+=raw.byteLength;
        const digest=toHex(await crypto.subtle.digest('SHA-256',raw));
        if(digest!==row.sha256)throw Error('full SHA-256 mismatch');
        shaVerified++;
        const blob=new Blob([raw],{type:response.headers.get('content-type')||'image/jpeg'});
        const url=URL.createObjectURL(blob);
        try{
          const img=new Image();
          img.src=url;
          await img.decode();
          if(img.naturalWidth!==row.width||img.naturalHeight!==row.height)
            throw Error('decoded dimensions differ from catalog');
          decoded++;
        }finally{URL.revokeObjectURL(url)}
      }
      await Promise.all(Array.from({length:3},async()=>{
        while(true){
          const i=cursor++;
          if(i>=rows.length)break;
          try{await check(rows[i])}
          catch(e){failures.push({album:rows[i].album,sha:rows[i].sha256.slice(0,16),error:String(e).slice(0,180)})}
        }
      }));
      return {expected:expected.size,read:rows.length,decoded,shaVerified,totalBytes,failures};
    }""")
    print("RECOVERED_PAGES_115_SHA_AND_DECODE",json.dumps(result,ensure_ascii=False),flush=True)
    assert result["expected"]==115 and result["read"]==115
    assert result["decoded"]==115 and result["shaVerified"]==115,(result["decoded"],result["shaVerified"],result["failures"])
    assert not result["failures"],result["failures"]
    context.close()


if __name__=="__main__":
    parser=argparse.ArgumentParser()
    parser.add_argument('--browser',choices=('chromium','webkit'),required=True)
    args=parser.parse_args()
    with sync_playwright() as p:
        browser=getattr(p,args.browser).launch(headless=True)
        try:run(browser)
        finally:browser.close()
    print("RECOVERED_PAGES_115_REAL_BYTES_VERIFIED",args.browser,flush=True)
