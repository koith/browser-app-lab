"""Read-only public search-index reachability probe: URLs/counts only, no user content."""
import json, re, urllib.parse, urllib.request, xml.etree.ElementTree as ET
from collections import Counter

TERMS=("뒷계","섹트","일탈계")
SITES=("x.com","threads.com")
for site in SITES:
    for term in TERMS:
        query=f'site:{site} "{term}"'
        url="https://www.bing.com/search?format=rss&q="+urllib.parse.quote(query)
        try:
            req=urllib.request.Request(url,headers={"User-Agent":"Mozilla/5.0 (compatible; IntersectionResearchProbe/1.0)","Accept":"application/rss+xml,application/xml"})
            with urllib.request.urlopen(req,timeout=14) as response:
                body=response.read(150000)
                root=ET.fromstring(body)
                links=[(n.text or "") for n in root.findall(".//item/link")]
                matching=[s for s in links if re.search(r"https?://(?:www\\.)?"+re.escape(site)+r"/",s)]
                print(json.dumps({"source":"bing_rss","site":site,"term":term,"http":response.status,"rss_items":len(links),"verified_domain_links":len(matching),"result_domains":dict(Counter(urllib.parse.urlsplit(s).hostname for s in links).most_common(5))},ensure_ascii=False))
        except Exception as error:
            print(json.dumps({"source":"bing_rss","site":site,"term":term,"error":str(error)[:100]},ensure_ascii=False))
