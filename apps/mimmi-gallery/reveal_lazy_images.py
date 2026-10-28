#!/usr/bin/env python3
"""Load normal, public, lazily-rendered album images with real browser scroll.

No click into download, login, subscription or challenge controls. The collector
visits only the provided PUBLIC album page; it does not synthesize protected URLs.
"""
from __future__ import annotations
from urllib.parse import urljoin
from collect_pixibb_public import safe_page,safe_photo

JS = r"""() => {
  const root=document.querySelector('article') || document.querySelector('main') || document;
  const all=[];
  for(const el of root.querySelectorAll('img,source,a[href]')){
    if(el.tagName.toLowerCase()==='a'){
      all.push(el.getAttribute('href')||'');
    }else{
      for(const k of ['currentSrc','src','data-src','data-original','data-full','data-lazy-src','srcset','data-srcset']){
        const v=k==='currentSrc'?el.currentSrc:el.getAttribute(k);
        if(v)all.push(...(k.includes('srcset')?v.split(',').map(x=>x.trim().split(/\s+/)[0]):[v]));
      }
    }
  }
  return {urls:all,height:document.documentElement.scrollHeight,
          bottom:scrollY+innerHeight>=document.documentElement.scrollHeight-80,
          scrollY};
}"""

def reveal(url,album,max_scrolls=26):
    if not safe_page(url,album):raise ValueError("Not a known public Mimmi album page")
    from playwright.sync_api import sync_playwright
    results=[];seen=set();stable=0
    with sync_playwright() as p:
        browser=p.chromium.launch(headless=True,args=["--disable-dev-shm-usage"])
        try:
            page=browser.new_page(viewport={"width":1100,"height":900},
                                  service_workers="block")
            page.goto(url,wait_until="domcontentloaded",timeout=35000)
            for _ in range(max_scrolls):
                state=page.evaluate(JS)
                before=len(results)
                for raw in state["urls"]:
                    v=urljoin(page.url,raw)
                    if safe_photo(v) and v not in seen:
                        seen.add(v);results.append(v)
                stable=stable+1 if len(results)==before else 0
                if stable>=4 and state["bottom"]:break
                page.evaluate("window.scrollBy(0, Math.max(500, window.innerHeight*0.85))")
                page.wait_for_timeout(320)
            return results
        finally:
            browser.close()

if __name__=="__main__":
    import argparse,json
    p=argparse.ArgumentParser()
    p.add_argument("page")
    p.add_argument("album")
    o=p.parse_args()
    print(json.dumps({"visible_lazy_urls":reveal(o.page,o.album)},ensure_ascii=False))
