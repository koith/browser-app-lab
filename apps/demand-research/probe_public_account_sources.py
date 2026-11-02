"""Small anonymous public-source account-feed check (aggregate-only).

Only sources documented as allowing public reads, with official public sample
profiles. No user-account data, URLs, IDs or text emitted. Never attempts
authentication, retry evasion, or private feeds.
"""
import json,urllib.parse,urllib.request,urllib.error
from datetime import datetime,timezone
UA="IntersectionPublicAccountVerification/1.0"

def fetch(url):
 try:
  req=urllib.request.Request(url,headers={"User-Agent":UA,"Accept":"application/json"})
  with urllib.request.urlopen(req,timeout=15) as r:
   raw=r.read(1500000);return r.status,json.loads(raw)
 except urllib.error.HTTPError as e:return e.code,{}
 except Exception:return 0,{}

def main():
 query=urllib.parse.urlencode({"actor":"bsky.app","limit":12,"filter":"posts_no_replies"})
 code,data=fetch("https://public.api.bsky.app/xrpc/app.bsky.feed.getAuthorFeed?"+query)
 rows=data.get("feed",[]) if isinstance(data,dict) else []
 verified=[r for r in rows if isinstance(r,dict) and isinstance(r.get("post"),dict) and
  not r.get("reason") and isinstance(r["post"].get("record",{}).get("text"),str)]
 print(json.dumps({"adapter":"bluesky_public_author","http":code,"items":len(rows),
  "public_original_text_records":len(verified),
  "with_date":sum(bool(x["post"]["record"].get("createdAt")) for x in verified)}),flush=True)
 acctcode,acct=fetch("https://mastodon.social/api/v1/accounts/lookup?acct=Mastodon")
 accountId=str(acct.get("id") or "") if isinstance(acct,dict) else ""
 postsCode,posts=(0,[])
 if acctcode==200 and accountId.isdigit():
  postsCode,posts=fetch("https://mastodon.social/api/v1/accounts/"+
   urllib.parse.quote(accountId,safe="")+"/statuses?limit=12&exclude_reblogs=true")
 items=posts if isinstance(posts,list) else []
 public=[s for s in items if isinstance(s,dict) and s.get("visibility")=="public"
   and str(s.get("account",{}).get("id") or "")==accountId and not s.get("reblog")]
 print(json.dumps({"adapter":"mastodon_public_author","account_lookup_http":acctcode,
  "public_statuses_http":postsCode,"items":len(items),"public_verified":len(public),
  "dated":sum(bool(s.get("created_at")) for s in public)}),flush=True)
if __name__=="__main__":main()
