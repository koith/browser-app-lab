"""Read-only, count-only SearXNG reachability check. Never retain snippets/users/posts.

Public metasearch instances are probes only, not guaranteed or endorsed production APIs.
At most 4 requests per site; failures do not trigger retries or proxy hopping.
"""
import concurrent.futures, html, json, re, urllib.parse, urllib.request
INSTANCES=("https://priv.au","https://searx.ononoki.org","https://searxng.site")
QUERIES=(("x","섹트"),("threads","일탈계"))
def run(instance,platform,term):
    target="x.com/status/" if platform=="x" else "threads.com/@"
    q=f'site:{target} "{term}"'
    url=instance+"/search?"+urllib.parse.urlencode({"q":q,"format":"json"})
    try:
        req=urllib.request.Request(url,headers={"User-Agent":"IntersectionPublicProbe/1.0","Accept":"application/json"})
        with urllib.request.urlopen(req,timeout=10) as response:
            content=response.read(350000)
            value=json.loads(content)
            results=value.get("results",[]) if isinstance(value,dict) else []
            links=[str(r.get("url","")) for r in results if isinstance(r,dict)]
            n=sum(bool(re.search(r"https://(?:www\.)?(?:x\.com|twitter\.com)/[^/\s]+/status/\d+",u)) for u in links) if platform=="x" else sum("threads.com/@" in u and "/post/" in u for u in links)
            return {"instance":urllib.parse.urlsplit(instance).hostname,"source":platform,"term":term,"http":response.status,"total_search_results":len(results),"canonical_post_links":n}
    except Exception as error:
        return {"instance":urllib.parse.urlsplit(instance).hostname,"source":platform,"term":term,"error":str(error)[:90]}
with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
    jobs=[(site,p,t) for site in INSTANCES for p,t in QUERIES]
    for result in pool.map(lambda x:run(*x),jobs):
        print(json.dumps(result,ensure_ascii=False))
