"""Bing image-URL visual search: structured PagesIncluding, not search HTML.

The ordinary Bing /images/search HTML page is *not* reverse visual evidence:
it contains hundreds of unrelated navigation links. Only PagesIncluding from
the JSON image knowledge response carries actual host-page attribution.

The current unauthenticated Bing web endpoint can change or reject requests.
On 403/404/challenge, return a precise unavailable status; never retry with
cookies, bypass a challenge or claim a confirmed reverse-image match.
"""
from __future__ import annotations
import json
from urllib.parse import quote_plus

import requests
from reverse_image_discovery import untrack

BING_ENDPOINT="https://www.bing.com/images/api/custom/knowledge"
WEB_URL="https://www.bing.com/images/search"
HEADERS={"User-Agent":"PersonalPublicPhotoSourceResearch/1.0",
         "Accept":"application/json"}

def pages_including(payload):
    """Extract only same-image host pages, never SimilarImages/ads/nav links."""
    if not isinstance(payload,dict):
        return [],False
    tags=payload.get("tags",[])
    if not isinstance(tags,list):
        return [],False
    results=[]
    seen=set()
    found_module=False
    for tag in tags[:10]:
        if not isinstance(tag,dict):
            continue
        for action in tag.get("actions",[])[:24]:
            if not isinstance(action,dict) or action.get("actionType")!="PagesIncluding":
                continue
            found_module=True
            data=action.get("data",{})
            values=data.get("value",[]) if isinstance(data,dict) else []
            if not isinstance(values,list):
                continue
            for photo in values[:100]:
                if not isinstance(photo,dict):
                    continue
                original=photo.get("hostPageUrl")
                page=untrack(original) if isinstance(original,str) else None
                if page is None or page in seen:
                    continue
                seen.add(page)
                asset=photo.get("contentUrl")
                results.append({
                    "url":page,
                    "label":str(photo.get("name") or "")[:200],
                    "matched_image_url":asset if isinstance(asset,str)
                        and asset.startswith("https://") else None,
                    "matched_width":photo.get("width"),
                    "matched_height":photo.get("height"),
                    "source_engine":"bing_visual_pages_including",
                })
    return results,found_module

def bing_visual_query(client,image_url):
    """One bounded public POST. Never upload local bytes or follow redirects."""
    if not isinstance(image_url,str) or not image_url.startswith("https://"):
        return {"status":"invalid_public_photo_url","links":[]}
    if not hasattr(client,"post"):
        return {"status":"post_not_supported","links":[]}
    referer=(WEB_URL+"?view=detailv2&iss=sbi&FORM=SBIHMP&sbisrc=UrlPaste"
             "&q=imgurl:"+quote_plus(image_url)+"&idpbck=1")
    body={"imageInfo":{"url":image_url,"source":"Url"}}
    try:
        response=client.post(
            BING_ENDPOINT,
            params={"iss":"sbi","FORM":"SBIHMP","mkt":"en-us"},
            files={"knowledgeRequest":(None,json.dumps(body),"application/json")},
            headers={**HEADERS,"Referer":referer},
            timeout=(9,26),allow_redirects=False)
    except requests.RequestException as exc:
        return {"status":"network_"+type(exc).__name__,"links":[]}
    if response.status_code in (301,302,303,307,308):
        return {"status":"redirect_not_followed","links":[]}
    if response.status_code!=200:
        return {"status":"http_"+str(response.status_code),"links":[]}
    if "json" not in response.headers.get("Content-Type","").lower():
        return {"status":"not_json","links":[]}
    if len(response.content)>4_500_000:
        return {"status":"oversized","links":[]}
    try:
        payload=response.json()
    except (ValueError,TypeError):
        return {"status":"invalid_json","links":[]}
    rows,found_module=pages_including(payload)
    if not found_module:
        return {"status":"no_pages_including_module","links":[]}
    return {"status":"visual_pages_"+str(len(rows)),"links":rows}
