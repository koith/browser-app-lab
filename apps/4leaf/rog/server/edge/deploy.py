#!/usr/bin/env python3
"""Deploy only the isolated free 4LEAF Worker via official script APIs.
Never alter gallery, subscriptions, domains, or another Worker.
"""
import json, os, pathlib, re, secrets, sys, urllib.request, urllib.error
NAME="fourleaf-central-chat-free"
ACCOUNT=os.environ["CLOUDFLARE_ACCOUNT_ID"].strip()
TOKEN=os.environ["CLOUDFLARE_API_TOKEN"].strip()
assert re.fullmatch("[a-f0-9]{32}",ACCOUNT) and TOKEN
ROOT="https://api.cloudflare.com/client/v4/accounts/"+ACCOUNT+"/"
def call(path,method="GET",payload=None,multipart=None,missing=False):
    headers={"Authorization":"Bearer "+TOKEN,"Accept":"application/json"}
    body=None
    if payload is not None:
        body=json.dumps(payload).encode();headers["Content-Type"]="application/json"
    if multipart:
        headers["Content-Type"],body=multipart
    request=urllib.request.Request(ROOT+path,data=body,headers=headers,method=method)
    try:
        with urllib.request.urlopen(request,timeout=40) as response: result=json.load(response)
    except urllib.error.HTTPError as error:
        result=json.loads(error.read())
        codes=[entry.get("code") for entry in result.get("errors",[])]
        if missing and (error.code==404 or 10007 in codes): return None
        raise RuntimeError(f"{method} {path}: HTTP {error.code}, codes {codes}") from None
    if result.get("success") is not True: raise RuntimeError(f"{method} {path}: {result.get('errors')}")
    return result
billing=call("subscriptions")
rows=billing.get("result")
assert rows==[] and billing.get("result_info",{}).get("total_count",0)==0,"Free default account not established"
worker=call("workers/workers/"+NAME,missing=True)
scripts=call("workers/scripts")["result"]
existing=next((entry for entry in scripts if entry.get("id")==NAME),None)
if worker is None:
    created=call("workers/workers","POST",{"name":NAME,"tags":["fourleaf-chat-authority"],"observability":{"enabled":False},"logpush":False})["result"]
    assert created.get("name")==NAME and re.fullmatch("[a-f0-9]{32}",created.get("id","")),"Created Worker identity unverified"
    print("Exact isolated Worker resource created",flush=True)
bundle=pathlib.Path(sys.argv[1])
modules=[x for x in bundle.iterdir() if x.suffix in (".js",".mjs")]
assert len(modules)==1, f"Expected one bundled executable module, got {[x.name for x in modules]}"
module=modules[0]
metadata={"main_module":module.name,"compatibility_date":"2026-11-01","compatibility_flags":["nodejs_compat"],"bindings":[{"name":"CHAT","type":"durable_object_namespace","class_name":"ChatAuthority"}],"tags":["fourleaf-chat-authority"]}
tag=existing.get("migration_tag") if existing else None
if tag and tag!="v1":raise RuntimeError("Unexpected durable object migration tag; refuse to overwrite")
if not tag:metadata["migrations"]={"new_tag":"v1","new_sqlite_classes":["ChatAuthority"]}
boundary="leaf-"+secrets.token_hex(24)
body=b""
for name,mime,value in [("metadata","application/json",json.dumps(metadata).encode()),(module.name,"application/javascript+module",module.read_bytes())]:
    body+=(f'--{boundary}\r\nContent-Disposition: form-data; name="{name}"; filename="{name}"\r\nContent-Type: {mime}\r\n\r\n').encode()+value+b"\r\n"
body+=f"--{boundary}--\r\n".encode()
result=call("workers/scripts/"+NAME,"PUT",multipart=("multipart/form-data; boundary="+boundary,body))["result"]
print("Worker upload acknowledged",result.get("id"),result.get("migration_tag"),flush=True)
route=call("workers/scripts/"+NAME+"/subdomain","POST",{"enabled":True,"previews_enabled":False})["result"]
assert route.get("enabled") is True
domain=call("workers/subdomain")["result"]["subdomain"]
assert domain=="gallery-9f7d03138f3f","Unexpected account workers.dev subdomain"
assert any(entry.get("id")==NAME for entry in call("workers/scripts")["result"]),"Actual Worker missing"
print("Verified Worker route https://"+NAME+"."+domain+".workers.dev",flush=True)
