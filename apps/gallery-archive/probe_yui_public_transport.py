#!/usr/bin/env python3
"""Normal public-origin transport diagnosis; no credentials or image saves."""
import sys
from pathlib import Path
from urllib.parse import urlsplit

import requests
from PIL import Image, ImageStat
from bs4 import BeautifulSoup
from direct_photo_pipeline import page_images
from io import BytesIO

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'yui-gallery'))
from public_photo_archive import PublicSession, public_failure

SAMPLES=[
    'https://showartx.net/artgravia-vol-693-yui/',
    'https://showartx.net/wp-content/uploads/2025/10/ART_693_3.jpg',
    'https://www.nicesss.com/archives/mij/artgravia/469248.html',
    'https://www.nicewww.com/wp-content/uploads/2026/05/1778813739-c81e728d9d4c2f6.jpg',
    'https://www.8kcosplay.com/artgravia-vol-677-yui%EC%9C%A0%EC%9D%B4/',
    'https://img119.imagetwist.com/th/77528/1lb5mywj6g45.jpg',
    'https://kgravure.vip/en/sets/yui-%EC%9C%A0%EC%9D%B4-artgravia-vol-663/',
    'https://wakobox.top/wp-content/uploads/2026/06/KOR06D087_1.webp',
]

def inspect(url):
    s=PublicSession(delay=0)
    host=urlsplit(url).hostname
    row={'host':host,'path':urlsplit(url).path}
    try:
        r=s.get(url)
        row.update(public_session_status=r.status_code,
                   public_session_type=r.headers.get('Content-Type','').split(';')[0],
                   public_session_bytes=len(r.content))
        if urlsplit(url).hostname=='www.nicesss.com' and r.headers.get('Content-Type','').lower().startswith('text/html'):
            bs=BeautifulSoup(r.content,'html.parser')
            urls,pages,status=page_images(r.content,url,'yui')
            row.update(parser_status=status,parser_photo_count=len(urls),
                page_heading=(bs.select_one('h1').get_text(' ',strip=True)[:90] if bs.select_one('h1') else None),
                candidate_sections={css:len(bs.select(css)) for css in ('article','.entry-content','.article-content','.post-content','.entry','.post')},
                native_preview_img_count=sum('nicewww.com/wp-content/uploads/2026/05/' in (im.get('src') or '') for im in bs.select('img')))
        if r.headers.get('Content-Type','').lower().startswith('image/'):
            with Image.open(BytesIO(r.content)) as im:
                im.load();row.update(image_dimensions=(im.width,im.height),image_format=im.format,
                    image_sample_stddev=round(max(ImageStat.Stat(im.convert('RGB').resize((32,32))).stddev),2))
    except Exception as e:
        row.update(public_session_error=type(e).__name__, public_session_details=public_failure(e))
    row['robots_status']=s.robot_status
    # Independent plain HTTP layer to distinguish origin denial, broken
    # robot policy and PublicSession implementation errors. No retries, no
    # auth, no login, redirects disabled, no bytes saved.
    try:
        r=requests.get(url,timeout=(8,18),allow_redirects=False,
                       headers={'User-Agent':'PersonalPublicPhotoSourceResearch/1.0'},
                       stream=True)
        row.update(plain_status=r.status_code,
                   plain_type=r.headers.get('Content-Type','').split(';')[0],
                   redirect_host=urlsplit(r.headers.get('Location','')).hostname)
        r.close()
    except requests.RequestException as e:
        row['plain_error']=type(e).__name__
    print('PUBLIC_SOURCE_TRANSPORT_DIAGNOSTIC',row,flush=True)

if __name__=='__main__':
    for url in SAMPLES:inspect(url)
