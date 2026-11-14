#!/usr/bin/env python3
"""Can actual archived 2013 4LEAF card screenshot faces be matched to
the already-extracted original 2002 CardData/chm_N.png pixels? Research-only.
A high ranking score is NOT a verified original CHR to CardData index until
uniqueness, pixel identity, exact face overlap and all 97 sources pass.
Never label an uncertain or generated face as a source card portrait.
"""
from pathlib import Path
from urllib.parse import unquote
import requests, numpy as np, cv2, json, io
from PIL import Image
root=Path(__file__).resolve().parents[1]
reference=(
 "https://postfiles.pstatic.net/20130109_261/"
 "kimmin9296_1357738112505vUuYR_JPEG/"
 "V-%C7%C3%B6%FB%B5%E5%B8%A3.png"
)
headers={"User-Agent":"Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/121 Safari/537.36",
 "Referer":"https://blog.naver.com/kimmin9296/175384849",
 "Accept":"image/avif,image/webp,image/apng,image/png,image/*;q=0.8,*/*;q=0.5"}
def read_url():
 errs=[]
 for url in [reference,reference+"?type=original",reference+"?type=w773",reference+"?type=w80_blur"]:
  try:
   r=requests.get(url,headers=headers,timeout=12)
   if r.ok and r.headers.get("content-type","").lower().startswith("image/") and len(r.content)>3000:
    return Image.open(io.BytesIO(r.content)).convert("RGB"),{"url":url,"http":r.status_code,"bytes":len(r.content),"mime":r.headers.get("content-type")}
   errs.append({"url":url,"http":r.status_code,"bytes":len(r.content),"type":r.headers.get("content-type")})
  except Exception as e:errs.append({"url":url,"error":str(e)[:180]})
 raise ValueError(json.dumps(errs,ensure_ascii=False))
im,origin=read_url()
screenshot=cv2.cvtColor(np.array(im),cv2.COLOR_RGB2GRAY)
paths=list(sorted((root/"original/CardData").glob("chm_*.png")))
assert len(paths)==97,len(paths)
candidates=[]
for f in paths:
 art=Image.open(f).convert("RGBA")
 pixel=np.array(art)
 alpha=pixel[:,:,3]
 rgb=cv2.cvtColor(pixel[:,:,:3],cv2.COLOR_RGB2GRAY)
 best={"score":-1,"scale":0,"location":None}
 for scale in [.75,.85,1.0,1.15,1.3,1.5,1.8,2.0,2.5]:
  w=max(4,round(rgb.shape[1]*scale));h=max(4,round(rgb.shape[0]*scale))
  if w>screenshot.shape[1] or h>screenshot.shape[0]:continue
  crop=cv2.resize(rgb,(w,h),interpolation=cv2.INTER_AREA if scale<1 else cv2.INTER_LINEAR)
  mask=cv2.resize(alpha,(w,h),interpolation=cv2.INTER_NEAREST)
  try:
   match=cv2.matchTemplate(screenshot,crop,cv2.TM_CCORR_NORMED,mask=mask)
   _,value,_,position=cv2.minMaxLoc(match)
   if np.isfinite(value) and value>best["score"]:
    best={"score":round(float(value),5),"scale":scale,"location":list(position)}
  except cv2.error:continue
 candidates.append({"carddata":f.name,**best})
candidates.sort(key=lambda x:x["score"],reverse=True)
result={"sourceArticle":"https://blog.naver.com/kimmin9296/175384849",
 "publishedCardName":"플랑드르 (Valuable)","verifiedOriginalCHR":"0043",
 "sourceImage":origin,"imageDimensions":list(im.size),
 "method":"OpenCV masked normalized cross-correlation, source screenshot x 97 independent CardData/chm_N PNGs",
 "topTwenty":candidates[:20],
 "bestGap":round(candidates[0]["score"]-candidates[1]["score"],5),
 "resultStatus":"CANDIDATE_SCORES_ONLY-NOT_SOURCE_ID_VERIFIED"}
out=Path("leaf-r31-original-carddata-portrait-source-match.json")
out.write_text(json.dumps(result,indent=2,ensure_ascii=False)+"\n")
print("R31_NATIVE_CARDDATA_VS_ARCHIVED_FACE_MATCH_CANDIDATES",json.dumps(result,ensure_ascii=False))
