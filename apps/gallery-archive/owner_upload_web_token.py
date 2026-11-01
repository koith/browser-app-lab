"""Reuse the EXISTING owner gateway's normal authenticated TeraBox /main token.

The pinned TeraBox rclone backend expects JSTOKEN for individual uploads. It
must come only from the owner's ordinary authenticated web page; never guess
tokens, fetch login-protected photos, execute third-party scripts, or route
credentials to an unrelated destination.
"""
from __future__ import annotations
import argparse
import asyncio
import os
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'apps/mimmi-gallery/cloud/gateway'))
from cookie_format import cookie_header
from terabox_web_state import OwnerUploadState,WebStateUnavailable

_ALLOWED_ORIGIN='https://www.terabox.com'


def obtain_cookie_and_token(cookie=None,state=None):
    raw=cookie if cookie is not None else os.environ.get('RCLONE_CONFIG_ARCHIVE_COOKIE','')
    header=cookie_header(raw)
    if not header:
        raise WebStateUnavailable('Owner archive cookie absent')
    token=asyncio.run((state or OwnerUploadState()).get(header,_ALLOWED_ORIGIN))
    if not token or any(ch in token for ch in ('\n','\r','\x00')):
        raise WebStateUnavailable('Owner upload token invalid')
    return header,token


def update_current_process(cookie=None,state=None):
    header,token=obtain_cookie_and_token(cookie,state)
    os.environ['RCLONE_CONFIG_ARCHIVE_COOKIE']=header
    os.environ['RCLONE_CONFIG_ARCHIVE_JSTOKEN']=token
    return token


def write_github_env(destination,cookie=None,state=None):
    header,token=obtain_cookie_and_token(cookie,state)
    target=Path(destination)
    if not target.is_file():
        raise ValueError('GitHub Actions environment destination unavailable')
    # GitHub's masking command is the only stdout use of the secret.
    print('::add-mask::'+token,flush=True)
    with target.open('a',encoding='utf-8') as out:
        out.write('RCLONE_CONFIG_ARCHIVE_JSTOKEN='+token+'\n')
    print('OWNER_WEB_UPLOAD_TOKEN_CONFIGURED',True,
          'OWNER_SESSION_COOKIE_RETAINED',bool(header),
          'TOKEN_OUTPUT',False,flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser()
    p.add_argument('--github-env',type=Path,required=True)
    p.add_argument('--best-effort',action='store_true',
                   help='Preserve the existing exact-SHA owner-cookie path if /main is unavailable')
    a=p.parse_args()
    try:
        write_github_env(a.github_env)
    except (WebStateUnavailable,OSError,TimeoutError) as exc:
        if not a.best_effort:
            raise
        print('OWNER_WEB_TOKEN_OPTIONAL_UNAVAILABLE',type(exc).__name__,
              'EXISTING_OWNER_COOKIE_UPLOAD_REQUIRES_EXACT_SHA',True,flush=True)
