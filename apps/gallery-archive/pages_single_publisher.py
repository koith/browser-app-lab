"""Honor the existing Pages mode without admin changes or competing deploys."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import time
from urllib.error import HTTPError,URLError
from urllib.request import Request,urlopen
from pages_deployment_identity import REPO,validate

STAMP='https://koith.github.io/browser-app-lab/gallery-deployment.json'

def publisher(config):
    if config.get('build_type')=='workflow':return 'workflow'
    if config.get('build_type')=='legacy' and config.get('source')=={'branch':'main','path':'/'}:
        return 'native'
    raise ValueError('Pages mode/source does not match this repository main root')

def pages_api(method='GET',suffix=''):
    # The job token already has Pages write/read, never administration.
    token=os.environ['GH_TOKEN']
    request=Request('https://api.github.com/repos/'+REPO+'/pages'+suffix,
        headers={'Authorization':'Bearer '+token,'Accept':'application/vnd.github+json',
                 'X-GitHub-Api-Version':'2022-11-28'},method=method)
    with urlopen(request,timeout=30) as response:
        body=response.read()
        return json.loads(body) if body else None

def exact_source():
    source=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip()
    if source!=os.environ.get('GITHUB_SHA') or os.environ.get('GITHUB_REPOSITORY')!=REPO:
        raise ValueError('Publisher checkout/trigger identity differs')
    return source

def wait_native(source):
    # The pre-existing deployment window is 30 minutes. This observes the one
    # native publisher; it never uploads a second competing photo artifact.
    deadline=time.monotonic()+1800
    last=None
    while time.monotonic()<deadline:
        try:
            with urlopen(STAMP,timeout=30) as response:raw=response.read()
            observed=validate(raw,source)
            if observed.get('build_kind')!='github-pages-jekyll':
                raise ValueError('Expected the selected native publisher')
            print('NATIVE_PAGES_EXACT_SOURCE_VISIBLE',source,flush=True)
            return
        except (HTTPError,URLError,ValueError) as error:
            state=str(error)
            if state!=last:print('WAITING_FOR_NATIVE_PAGES_SOURCE',state[:200],flush=True);last=state
        time.sleep(15)
    raise TimeoutError('Native Pages did not expose the exact committed source identity')

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--select',type=Path);p.add_argument('--wait-native',action='store_true');args=p.parse_args()
    source=exact_source()
    if args.select:
        selected=publisher(pages_api())
        with args.select.open('a') as stream:stream.write('publisher='+selected+'\n')
        print('EXISTING_PAGES_SINGLE_PUBLISHER',selected,flush=True)
    elif args.wait_native:
        if publisher(pages_api())!='native':raise ValueError('Native publisher mode changed')
        if os.environ.get('GITHUB_EVENT_NAME')=='workflow_dispatch':pages_api('POST','/builds')
        wait_native(source)
    else:p.error('Choose --select or --wait-native')
