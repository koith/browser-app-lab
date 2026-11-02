"""Free FxEmbed v2 X full-text search feasibility, bounded and aggregate-only.

Docs: https://docs.fxembed.com/api/twitter/operations/2search/
No credentials, logins, media, post IDs, author names, or text printed.
"""
import json, urllib.request, urllib.error, urllib.parse
from datetime import datetime, timezone, timedelta
for label,term in (("project","섹트"),("control","coffee")):
    url="https://api.fxtwitter.com/2/search?"+urllib.parse.urlencode({"q":term,"feed":"latest","count":10})
    out={"provider":"fxembed_v2_search","term":label}
    req=urllib.request.Request(url,headers={"User-Agent":"IntersectionFreeXResearch/1.0",
                                              "Accept":"application/json"})
    try:
        with urllib.request.urlopen(req,timeout=20) as r:
            out["http"]=r.status
            data=json.loads(r.read(350000))
            out["code"]=data.get("code")
            rows=data.get("results",[])
            out["rows"]=len(rows) if isinstance(rows,list) else 0
            if isinstance(rows,list):
                out["exact_term"]=sum(term in str(x.get("text","")) for x in rows if isinstance(x,dict))
                out["has_post_date"]=sum(bool(x.get("created_at") or x.get("created_timestamp")) for x in rows if isinstance(x,dict))
            out["is_error"]=bool(data.get("message")) and not out["rows"]
    except urllib.error.HTTPError as e:
        out.update(http=e.code,rows=0,error="HTTP denied")
    except Exception as e:
        out.update(http=0,rows=0,error=type(e).__name__)
    print(json.dumps(out,ensure_ascii=False),flush=True)
