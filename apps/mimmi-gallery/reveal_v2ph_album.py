#!/usr/bin/env python3
"""Read only visible, public V2PH album DOM images by normal browser scrolling.

No login, API token, pagination bypass, protected download buttons, or invented
image URLs. Actual bytes and SHA-256 are verified by collect_v2ph_public.
"""
from urllib.parse import urljoin,urlsplit
from collect_v2ph_public import safe_source,safe_photo

EVAL_IMAGES=r"""() => {
  const root=document.querySelector('article')||document.querySelector('main')||document;
  const urls=[];
  for(const el of root.querySelectorAll('img,source,a[href]')){
    if(el.tagName.toLowerCase()==='a'){
      urls.push(el.getAttribute('href')||'');
    }else{
      for(const k of ['currentSrc','src','data-original','data-src','data-lazy-src','data-full','srcset','data-srcset']){
        const value=k==='currentSrc'?el.currentSrc:el.getAttribute(k);
        if(!value)continue;
        urls.push(...(k.includes('srcset')?value.split(',').map(x=>x.trim().split(/\s+/)[0]):[value]));
      }
    }
  }
  const doc=document.documentElement;
  return {urls,scrollY:window.scrollY,
    bottom:window.scrollY+window.innerHeight>=doc.scrollHeight-110};
}"""

def reveal(url,album_url,max_scrolls=26):
    base=urlsplit(album_url)
    dest=urlsplit(url)
    if (not safe_source(url) or not safe_source(album_url)
        or dest.path!=base.path or not base.path.startswith("/album/")
        or not base.path.endswith(".html")):
        raise ValueError("Not a public album page for this V2PH source")
    from playwright.sync_api import sync_playwright
    found=[];seen=set();stable=0
    with sync_playwright() as p:
        browser=p.chromium.launch(headless=True,args=["--disable-dev-shm-usage"])
        try:
            page=browser.new_page(viewport={"width":1200,"height":900},service_workers="block")
            page.goto(url,wait_until="domcontentloaded",timeout=35000)
            final=urlsplit(page.url)
            if not safe_source(page.url) or final.path!=base.path:
                raise ValueError("Public album redirected outside expected work")
            for _ in range(max_scrolls):
                state=page.evaluate(EVAL_IMAGES)
                before=len(found)
                for raw in state["urls"]:
                    item=urljoin(page.url,raw)
                    if safe_photo(item) and item not in seen:
                        seen.add(item);found.append(item)
                stable=stable+1 if len(found)==before else 0
                if stable>=4 and state["bottom"]:break
                page.evaluate("window.scrollBy(0, Math.max(window.innerHeight*.88,600))")
                page.wait_for_timeout(300)
            return found
        finally:
            browser.close()
